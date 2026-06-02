//! Loading SHACL shapes from local file or HTTP URL.

use reqwest::Client;
use std::path::Path;
use std::time::Duration;

pub async fn load_shapes(path_or_url: &str) -> anyhow::Result<String> {
    if path_or_url.starts_with("http://") || path_or_url.starts_with("https://") {
        load_shapes_from_url(path_or_url).await
    } else {
        load_shapes_from_file(path_or_url)
    }
}

fn load_shapes_from_file(path: &str) -> anyhow::Result<String> {
    let content = std::fs::read_to_string(path)?;
    Ok(content)
}

async fn load_shapes_from_url(url: &str) -> anyhow::Result<String> {
    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .user_agent("shacl-validate-oxi/0.1 (DOOS)")
        .build()?;

    let resp = client.get(url).send().await?;
    if !resp.status().is_success() {
        anyhow::bail!("Failed to fetch shapes from {}: {}", url, resp.status());
    }
    let text = resp.text().await?;
    Ok(text)
}