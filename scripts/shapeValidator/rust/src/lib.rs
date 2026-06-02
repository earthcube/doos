//! Core library for the SHACL validator using Oxigraph + rudof.
//!
//! This crate provides the building blocks for a high-performance,
//! rate-limited SHACL validation pipeline that stores results in Oxigraph
//! with consistent skolemization (authority: http://gleaner.io).

pub mod shapes;
pub mod skolem;
pub mod sparql;

// Re-exports for convenience (Store may come from oxigraph or oxigraph::store depending on version)
pub use rudof_lib as rudof;