"""Script to download data from EU Funding & Tenders Portal."""
import logging
import os
from pathlib import Path
import sys

# Add parent directory to path to import data_sourcing
sys.path.append(str(Path(__file__).parent.parent))
from data_sourcing import FundingAndTenderPortal

def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup paths
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data_test"
    data_dir.mkdir(exist_ok=True)
    
    project_file = data_dir / "raw_projects.pkl"
    orga_file = data_dir / "raw_organizations.pkl"
    
    # Initialize and run download
    ft_portal = FundingAndTenderPortal(
        raw_project_data_filename=str(project_file),
        raw_orga_data_filename=str(orga_file)
    )
    
    # You can choose to suppress crawling if you want to use cached data
    suppress_crawl = False  # Set to True to use cached data
    
    print("Starting data download...")
    project_df, orga_df = ft_portal.update_source(suppress_crawl=suppress_crawl)
    
    print(f"\nDownload completed!")
    print(f"Projects downloaded: {len(project_df)}")
    print(f"Organizations downloaded: {len(orga_df)}")
    print(f"\nData saved to:")
    print(f"- Projects: {project_file}")
    print(f"- Organizations: {orga_file}")

if __name__ == "__main__":
    main()
