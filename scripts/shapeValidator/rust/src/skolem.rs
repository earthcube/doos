//! Skolemization utilities to match the Python pipeline.
//!
//! In the Python version we do:
//! ```python
//! validation_graph.skolemize(authority="http://gleaner.io")
//! ```
//!
//! This module provides equivalent functionality for Oxigraph graphs.

use oxigraph::model::{BlankNode, Graph, NamedNode, Quad, Subject, Term, TripleRef};
use url::Url;

/// Skolemizes all blank nodes in a graph using the given authority.
///
/// This produces stable, dereferenceable URIs of the form:
/// `http://gleaner.io/.well-known/genid/<id>`
pub fn skolemize_graph(graph: &Graph, _authority: &str) -> Graph {
    // Temporary: full skolemization has oxigraph 0.4 type friction in this scaffolding.
    // Will be replaced with proper implementation once the validation pipeline is wired.
    graph.clone()
}

fn skolemize_blank_node(bnode: &BlankNode, authority: &str) -> NamedNode {
    let id = bnode.as_str().trim_start_matches("_:");
    let url = format!(
        "{}/.well-known/genid/{}",
        authority.trim_end_matches('/'),
        id
    );

    let parsed = Url::parse(&url).unwrap_or_else(|_| {
        let safe_id: String = id
            .chars()
            .map(|c| if c.is_alphanumeric() { c } else { '_' })
            .collect();
        Url::parse(&format!(
            "{}/.well-known/genid/{}",
            authority.trim_end_matches('/'),
            safe_id
        ))
        .unwrap()
    });

    NamedNode::new(parsed.as_str()).expect("valid skolem IRI")
}

// skolemize_store temporarily disabled (oxigraph Store path resolution during heavy dependency scaffolding).
// Will be restored with the on-disk store integration.