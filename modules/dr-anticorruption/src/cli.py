import click
from src.config.config import config
from src.data.data_manager import data_manager
from src.data.migrate import migrate

@click.group()
@click.option('--config', default=None, help='Config path')
def cli(config_path):
    if config_path:
        from src.config.config import config
        config.reload(config_path)
    click.echo("DR Anti-Corruption CLI")

@cli.command()
@click.option('--target', default='all')
@click.option('--max-pages', type=int, default=None)
def ingest(target, max_pages):
    \"\"\"Run ingestion pipeline.\"\"\"
    from src.core.ingestion import main
    # Pass args
    import sys
    sys.argv = ['ingest', '--target', target]
    if max_pages:
        sys.argv += ['--max-pages', str(max_pages)]
    main()

@cli.command()
def migrate_data():
    \"\"\"Migrate JSON data to SQLite.\"\"\"
    migrate()
    click.echo("Migration complete")

@cli.command()
@click.option('--limit', default=10, type=int)
def risk_batch(limit):
    \"\"\"Run risk pipeline batch.\"\"\"
    from src.core.risk_pipeline import run_pipeline
    run_pipeline(limit=limit)

@cli.command()
def test_integration():
    \"\"\"Run integration tests.\"\"\"
    from src.core.test_integration import test_risk_engine
    test_risk_engine()

if __name__ == '__main__':
    cli()
