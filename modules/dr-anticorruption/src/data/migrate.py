import pandas as pd
import sqlite3
from pathlib import Path
import logging

from .data_manager import data_manager
from .database import db  # To init schema
from .models import Proveedor, Contrato  # For validation optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    data_dir = Path('data')
    db_path = data_dir / 'dr_anticorruption.db'

    with sqlite3.connect(db_path) as conn:
        # Init schema if not
        from .database import Database
        Database()

        # Proveedores
        proveedores = data_manager.load_latest('proveedores_full_*.json')
        if proveedores:
            df_prov = pd.DataFrame(proveedores)
            df_prov.to_sql('proveedores', conn, if_exists='replace', index=False)
            logger.info(f"Migrated {len(proveedores)} proveedores")

        # Contratos
        contratos = data_manager.load_latest('contratos_*.json')
        if contratos:
            df_contr = pd.DataFrame(contratos)
            df_contr.to_sql('contratos', conn, if_exists='replace', index=False)
            logger.info(f"Migrated {len(contratos)} contratos")

        # Persons relationships from latest
        persons_files = glob.glob('data/persons_*.json')
        if persons_files:
            latest_persons = max(persons_files, key=os.path.getmtime)
            with open(latest_persons, 'r') as f:
                persons_data = json.load(f)
            df_persons = pd.DataFrame(persons_data)
            df_persons.to_sql('persons', conn, if_exists='replace', index=False)
            logger.info(f"Migrated persons from {latest_persons}")

        relationships_files = glob.glob('data/relationships_*.json')
        if relationships_files:
            latest_rel = max(relationships_files, key=os.path.getmtime)
            with open(latest_rel, 'r') as f:
                rel_data = json.load(f)
            df_rel = pd.DataFrame(rel_data)
            df_rel.to_sql('relationships', conn, if_exists='replace', index=False)
            logger.info(f"Migrated relationships from {latest_rel}")

        # Forensic
        if Path('data/versatility_hits.json').exists():
            with open('data/versatility_hits.json') as f:
                vers = json.load(f)
            df_vers = pd.DataFrame(vers)
            df_vers['type'] = 'VERSATILITY'
            df_vers.to_sql('forensic_hits', conn, if_exists='append', index=False)

        if Path('data/activation_spikes.json').exists():
            with open('data/activation_spikes.json') as f:
                act = json.load(f)
            df_act = pd.DataFrame(act)
            df_act['type'] = 'ACTIVATION_SPIKE'
            df_act['score'] = df_act['concentration'] * 0.4  # Approx
            df_act['reason'] = df_act['reason'] if 'reason' in df_act else 'Spike'
            df_act.to_sql('forensic_hits', conn, if_exists='append', index=False)

        logger.info("Migration complete")

if __name__ == '__main__':
    migrate()
