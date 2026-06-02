use clap::Parser;
use shacl_validate_oxi::shapes::load_shapes;
use shacl_validate_oxi::skolem::skolemize_graph;
use shacl_validate_oxi::sparql::{SparqlClient, SparqlClientConfig};
use oxigraph::store::Store;
// rudof_lib integration (see comments in the loop for current API hints from the compiler)
use std::io::Write;
use std::path::Path;

/// High-performance SHACL validator.
///
/// Rust port of `validateToOxigraph.py` using:
/// - rudof for SHACL validation
/// - Oxigraph (on-disk) for result storage
/// - Tokio + rate limiting for polite parallel fetching
///
/// Subjects of ValidationReport and ValidationResult are always skolemized
/// with authority "http://gleaner.io" for consistency with the Python pipeline.
#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// SPARQL endpoint URL (e.g. http://ghost.lan:7007/sparql)
    endpoint: String,

    /// SHACL shapes file (local path or URL)
    shapefile: String,

    /// Output N-Quads file for validation results
    #[arg(short, long, default_value = "results.nq")]
    output: String,

    /// Process only the first N graphs (0 = all)
    #[arg(short, long, default_value_t = 0)]
    limit: usize,

    /// Maximum number of graphs to process concurrently
    #[arg(long, default_value_t = 8)]
    max_concurrent: usize,

    /// Maximum requests per second to the SPARQL endpoint (rate limiting)
    #[arg(long, default_value_t = 2.0)]
    requests_per_second: f64,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    tracing_subscriber::fmt::init();

    println!("=== shacl-validate-oxi (Rust) ===");
    println!("Endpoint:              {}", args.endpoint);
    println!("Shapes:                {}", args.shapefile);
    println!("Output:                {}", args.output);
    println!("Max concurrent:        {}", args.max_concurrent);
    println!("Rate limit:            {} req/s", args.requests_per_second);
    if args.limit > 0 {
        println!("Limit:                 {} graphs", args.limit);
    }
    println!();

    // 1. Load shapes (supports file or URL)
    println!("Loading shapes...");
    let shapes_ttl = load_shapes(&args.shapefile).await?;
    println!("Shapes loaded ({} bytes)", shapes_ttl.len());

    // 2. Create rate-limited SPARQL client
    let config = SparqlClientConfig {
        endpoint: args.endpoint.clone(),
        max_concurrent: args.max_concurrent,
        requests_per_second: args.requests_per_second,
        user_agent: "shacl-validate-oxi/0.1 (DOOS)".to_string(),
    };
    let client = SparqlClient::new(config)?;

    // 3. Get list of graphs
    println!("Fetching list of graphs from endpoint...");
    let mut graphs: Vec<String> = client.list_dataset_graphs().await?;
    if args.limit > 0 {
        graphs.truncate(args.limit);
    }
    println!("Found {} graphs to process.\n", graphs.len());

    // 4. Open on-disk Oxigraph store (recommended for large result sets)
    let store_dir = Path::new("./oxigraph-store");
    std::fs::create_dir_all(store_dir)?;
    let store = Store::open(store_dir)?;
    println!("On-disk Oxigraph store opened at {:?}", store_dir);

    // 5. rudof will be integrated here (shapes can be loaded once outside the loop for efficiency).
    // See the per-task comment for current compiler hints on the API.

    // 6. Concurrent processing with rate limiting
    let mut handles = vec![];
    let semaphore = std::sync::Arc::new(tokio::sync::Semaphore::new(args.max_concurrent));

    for (i, graph_uri) in graphs.into_iter().enumerate() {
        let client = client.clone();
        let store = store.clone();
        let sem = semaphore.clone();
        let shapes = shapes_ttl.clone();
        let endpoint = args.endpoint.clone(); // not strictly needed here

        let handle = tokio::spawn(async move {
            let _permit = sem.acquire().await.unwrap();

            // Fetch graph data (rate limited inside the SparqlClient)
            let data_ttl = match client.construct_graph(&graph_uri).await {
                Ok(t) => t,
                Err(e) => {
                    eprintln!("  [{}] Failed to fetch {}: {}", i, graph_uri, e);
                    return;
                }
            };

            // rudof instance will be created here when the exact API is plugged in.

            // === RUDOF INTEGRATION POINT ===
            // From compiler hints, the current API uses builders like:
            //   rudof.load_data()... or similar.
            // For a working skeleton we insert a marker so the store + dump path is exercised.
            println!("  [{}] (rudof integration pending — compiler suggests load_data() builder)", i);

            let marker = format!("<{}> <http://example.org/hasValidation> \"rudof-pending\" .", graph_uri);
            if let Err(e) = store.load_from_reader(oxigraph::io::RdfFormat::NTriples, marker.as_bytes()) {
                eprintln!("  [{}] Failed to insert marker for {}: {}", i, graph_uri, e);
            } else {
                println!("  [{}] Stored (rudof ready to plug in) {}", i, graph_uri);
            }
        });

        handles.push(handle);
    }

    // Wait for all
    for handle in handles {
        let _ = handle.await;
    }

    // 7. Dump the store to N-Quads (manual iteration for oxigraph 0.4 compatibility)
    println!("\nDumping results to {}...", args.output);
    let mut file = std::fs::File::create(&args.output)?;
    for quad in store.iter() {
        let quad = quad?;
        writeln!(file, "{} .", quad)?;
    }
    println!("Done. Results written to {}", args.output);

    Ok(())
}
