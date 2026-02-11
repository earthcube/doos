import sys
import dspy
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from typing import List, Tuple, Any
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from diskcache import FanoutCache
import requests
import asyncio
import aiohttp
from dataclasses import dataclass
import time


@dataclass
class ModelResult:
    model_name: str
    response: str
    execution_time: float
    error: str = None


@dataclass
class SPARQLResult:
    model_name: str
    query: str
    csv_result: str
    execution_time: float
    error: str = None


async def sparql_to_csv_async(
    session: aiohttp.ClientSession, url: str, query: str, model_name: str
) -> SPARQLResult:
    """Async version of SPARQL to CSV conversion"""
    headers = {"Accept": "text/csv"}
    params = {"query": query}

    start_time = time.time()
    try:
        async with session.get(url, headers=headers, params=params) as response:
            response.raise_for_status()
            csv_content = await response.text()
            execution_time = time.time() - start_time
            return SPARQLResult(model_name, query, csv_content, execution_time)

    except Exception as e:
        execution_time = time.time() - start_time
        return SPARQLResult(model_name, query, "", execution_time, str(e))


def sparql_to_csv(url: str, query: str) -> str:
    """Synchronous version (kept for compatibility)"""
    headers = {"Accept": "text/csv"}
    params = {"query": query}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"Error: {e}"


def get_model_response(
    model_config: Tuple[Any, str], context_data: str, question: str
) -> ModelResult:
    """Get response from a single model with timing and error handling"""
    model, model_name = model_config
    start_time = time.time()

    try:
        with dspy.context(lm=model):
            rag = dspy.ChainOfThought("context, question -> response")
            result = rag(context=context_data, question=question)
            execution_time = time.time() - start_time
            return ModelResult(model_name, result.response, execution_time)

    except Exception as e:
        execution_time = time.time() - start_time
        return ModelResult(model_name, "", execution_time, str(e))


def get_context_data():
    """Read context data from file"""
    try:
        with open("./patterns.txt", "r") as f:
            return f.read()
    except Exception as e:
        print(f"Error reading context file: {e}")
        sys.exit()
        return ""


def get_question():
    """Get the default question"""
    return """Using the provided context which represents triple patterns from the associated graph.
Generate a SPARQL query that finds all the possible ways a person can be associated with a dataset"""


async def process_sparql_queries_async(
    model_results: List[ModelResult], sparql_url: str
) -> List[SPARQLResult]:
    """Process SPARQL queries asynchronously"""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for result in model_results:
            if result.error is None and result.response:
                task = sparql_to_csv_async(
                    session, sparql_url, result.response, result.model_name
                )
                tasks.append(task)

        return await asyncio.gather(*tasks, return_exceptions=True)


def setup_models() -> List[Tuple[Any, str]]:
    """Setup and return all models with their names"""
    OAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    XAI_API_KEY = os.environ.get("XAI_API_KEY")
    NRP_API_KEY = os.environ.get("NRP_API_KEY")

    models = []

    # Only add models if API keys are available
    if OAI_API_KEY:
        models.extend(
            [
                # (dspy.LM("openai/gpt-4o-mini", api_key=OAI_API_KEY), "OpenAI 4o-mini"),
                (dspy.LM("openai/gpt-5", api_key=OAI_API_KEY), "OpenAI 5")
            ]
        )

    if XAI_API_KEY:
        models.extend(
            [
                (
                    dspy.LM(
                        "xai/grok-3-mini",
                        api_key=XAI_API_KEY,
                        api_base="https://api.x.ai/v1",
                        max_tokens=27000,
                    ),
                    "XAI Grok 3",
                ),
                (
                    dspy.LM(
                        "xai/grok-4-fast",
                        api_key=XAI_API_KEY,
                        api_base="https://api.x.ai/v1",
                        max_tokens=27000,
                    ),
                    "XAI Grok 4",
                ),
            ]
        )

    if NRP_API_KEY:
        models.extend(
            [
                (
                    dspy.LM(
                        "openai/qwen3",
                        api_key=NRP_API_KEY,
                        api_base="https://llm.nrp-nautilus.io",
                        max_tokens=10000,
                        stop=None,
                    ),
                    "NRP Qwen3",
                ),
                (
                    dspy.LM(
                        "openai/kimi",
                        api_key=NRP_API_KEY,
                        api_base="https://llm.nrp-nautilus.io",
                        max_tokens=10000,
                        stop=None,
                    ),
                    "NRP Kimi",
                ),
            ]
        )

    return models


def display_model_results(results: List[ModelResult]):
    """Display model results in a nice table"""
    console = Console()
    table = Table(title="Model Responses")
    table.add_column("Model", style="cyan")
    table.add_column("Response", style="magenta", no_wrap=False)
    table.add_column("Time (s)", style="green")
    table.add_column("Status", style="yellow")

    for result in results:
        status = (
            "✓ Success" if result.error is None else f"✗ Error: {result.error[:50]}..."
        )
        table.add_row(
            result.model_name,
            (
                result.response[:2000] + "..."
                if len(result.response) > 2000
                else result.response
            ),
            f"{result.execution_time:.2f}",
            status,
            end_section=True,
        )

    console.print(table)


def display_sparql_results(results: List[SPARQLResult]):
    """Display SPARQL execution results"""
    console = Console()
    table = Table(title="SPARQL Query Results")
    table.add_column("Model", style="cyan")
    table.add_column("CSV Result", style="green", no_wrap=False)
    table.add_column("Time (s)", style="yellow")
    table.add_column("Status", style="magenta")

    for result in results:
        if isinstance(result, Exception):
            table.add_row("Unknown", str(result)[:100], "N/A", "✗ Exception")
            continue

        status = (
            "✓ Success" if result.error is None else f"✗ Error: {result.error[:50]}..."
        )
        csv_preview = (
            result.csv_result[:100] + "..."
            if len(result.csv_result) > 100
            else result.csv_result
        )

        table.add_row(
            result.model_name,
            csv_preview,
            f"{result.execution_time:.2f}",
            status,
            end_section=True,
        )

    console.print(table)


async def main_async():
    """Main async function"""
    parser = argparse.ArgumentParser(description="Generate SPARQL queries using dspy.")
    parser.add_argument(
        "-q",
        "--question",
        type=str,
        default=get_question(),
        help="The question to ask the language model.",
    )
    parser.add_argument(
        "--sparql-url",
        type=str,
        default="http://ghost.lan:7007/sparql",
        help="SPARQL endpoint URL",
    )
    parser.add_argument(
        "--max-workers", type=int, default=6, help="Maximum number of worker threads"
    )
    args = parser.parse_args()

    # Setup caching
    dspy.configure(cache=True)
    cache_dir = "./dspy_cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache = FanoutCache(directory=cache_dir, timeout=1.0)
    dspy.configure(cache=cache)

    # Setup models
    model_configs = setup_models()

    if not model_configs:
        print(
            "No API keys found. Please set OPENAI_API_KEY, XAI_API_KEY, or NRP_API_KEY"
        )
        return

    # Get context data and question
    context_data = get_context_data()
    question = args.question  # Use the command line argument

    console = Console()

    # Phase 1: Get responses from all models in parallel
    console.print("🚀 [bold blue]Phase 1: Querying language models...[/bold blue]")

    with Progress() as progress:
        task = progress.add_task(
            "[green]Processing models...", total=len(model_configs)
        )

        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            # Submit all model queries with context and question
            future_to_model = {
                executor.submit(
                    get_model_response, config, context_data, question
                ): config[1]
                for config in model_configs
            }

            model_results = []
            for future in as_completed(future_to_model):
                model_name = future_to_model[future]
                try:
                    result = future.result()
                    model_results.append(result)
                    progress.update(task, advance=1)
                    console.print(f"✓ Completed: {model_name}")
                except Exception as e:
                    console.print(f"✗ Failed: {model_name} - {e}")
                    model_results.append(ModelResult(model_name, "", 0.0, str(e)))
                    progress.update(task, advance=1)

    # Display model results
    display_model_results(model_results)

    # Phase 2: Execute SPARQL queries asynchronously
    console.print("\n🔍 [bold blue]Phase 2: Executing SPARQL queries...[/bold blue]")

    # Filter out failed model results
    successful_results = [
        r for r in model_results if r.error is None and r.response.strip()
    ]

    if successful_results:
        sparql_results = await process_sparql_queries_async(
            successful_results, args.sparql_url
        )
        display_sparql_results(sparql_results)
    else:
        console.print("[red]No successful model responses to process[/red]")

    # Print summary statistics
    console.print("\n📊 [bold]Summary:[/bold]")
    console.print(f"   • Models queried: {len(model_configs)}")
    console.print(f"   • Successful responses: {len(successful_results)}")
    console.print(
        f"   • Total execution time: {sum(r.execution_time for r in model_results):.2f}s"
    )


def main():
    """Synchronous wrapper for the async main function"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")


if __name__ == "__main__":
    main()
