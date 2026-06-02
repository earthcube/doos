//! Rate-limited async SPARQL client for fetching graphs via CONSTRUCT.
//!
//! Designed to be polite to data providers while still allowing good throughput.

use governor::{Quota, RateLimiter};
use reqwest::Client;
use std::num::NonZeroU32;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::Semaphore;
use url::Url;

/// Configuration for the SPARQL client.
#[derive(Debug, Clone)]
pub struct SparqlClientConfig {
    pub endpoint: String,
    pub max_concurrent: usize,
    pub requests_per_second: f64,
    pub user_agent: String,
}

impl Default for SparqlClientConfig {
    fn default() -> Self {
        Self {
            endpoint: "http://localhost:7007/sparql".to_string(),
            max_concurrent: 8,
            requests_per_second: 2.0,
            user_agent: "shacl-validate-oxi/0.1 (DOOS project)".to_string(),
        }
    }
}

/// Async SPARQL client with built-in rate limiting and concurrency control.
#[derive(Clone)]
pub struct SparqlClient {
    client: Client,
    endpoint: Url,
    rate_limiter: Arc<RateLimiter<NotKeyed, InMemoryState, DefaultClock, NoOpMiddleware>>,
    semaphore: Arc<Semaphore>,
}

impl SparqlClient {
    pub fn new(config: SparqlClientConfig) -> anyhow::Result<Self> {
        let endpoint = Url::parse(&config.endpoint)?;

        let client = Client::builder()
            .user_agent(config.user_agent)
            .timeout(Duration::from_secs(60))
            .build()?;

        // Set up rate limiter using governor
        let quota = if config.requests_per_second > 0.0 {
            let permits = NonZeroU32::new(config.requests_per_second.ceil() as u32)
                .unwrap_or(NonZeroU32::new(1).unwrap());
            Quota::per_second(permits)
        } else {
            Quota::per_second(NonZeroU32::new(1000).unwrap()) // Effectively unlimited
        };

        let rate_limiter = Arc::new(RateLimiter::direct(quota));

        let semaphore = Arc::new(Semaphore::new(config.max_concurrent));

        Ok(Self {
            client,
            endpoint,
            rate_limiter,
            semaphore,
        })
    }

    /// Fetches a named graph via CONSTRUCT.
    ///
    /// Applies rate limiting before making the request.
    pub async fn construct_graph(&self, graph_uri: &str) -> anyhow::Result<String> {
        // Acquire rate limit token
        self.rate_limiter.until_ready().await;

        // Acquire concurrency slot
        let _permit = self.semaphore.acquire().await?;

        let query = format!(
            r#"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{}> {{ ?s ?p ?o }} }}"#,
            graph_uri
        );

        let response = self
            .client
            .post(self.endpoint.as_str())
            .header("Content-Type", "application/sparql-query")
            .header("Accept", "text/turtle")
            .body(query)
            .send()
            .await?;

        if !response.status().is_success() {
            let status = response.status();
            let text = response.text().await.unwrap_or_default();
            anyhow::bail!("SPARQL CONSTRUCT failed for {}: {} - {}", graph_uri, status, text);
        }

        let turtle = response.text().await?;
        Ok(turtle)
    }

    /// Lists all named graphs containing schema:Dataset (matching current Python query).
    pub async fn list_dataset_graphs(&self) -> anyhow::Result<Vec<String>> {
        self.rate_limiter.until_ready().await;

        let query = r#"
            SELECT ?g WHERE {
                GRAPH ?g { ?s a <https://schema.org/Dataset> }
            }
        "#;

        let response = self
            .client
            .post(self.endpoint.as_str())
            .header("Content-Type", "application/sparql-query")
            .header("Accept", "application/sparql-results+json")
            .body(query)
            .send()
            .await?;

        if !response.status().is_success() {
            anyhow::bail!("Failed to list graphs: {}", response.status());
        }

        #[derive(serde::Deserialize)]
        struct SparqlBindings {
            bindings: Vec<GraphBinding>,
        }

        #[derive(serde::Deserialize)]
        struct GraphBinding {
            g: GraphValue,
        }

        #[derive(serde::Deserialize)]
        struct GraphValue {
            value: String,
        }

        #[derive(serde::Deserialize)]
        struct SparqlResult {
            results: SparqlBindings,
        }

        let result: SparqlResult = response.json().await?;
        let graphs = result.results.bindings.into_iter().map(|b| b.g.value).collect();
        Ok(graphs)
    }
}

// Re-export governor types for convenience in main
pub use governor::state::{InMemoryState, NotKeyed};
pub use governor::middleware::NoOpMiddleware;
pub use governor::clock::DefaultClock;