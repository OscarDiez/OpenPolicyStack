"""
Entity Extractor Service for DR Anti-Corruption.
Extracts persons relationships from proveedores using composite keys.
"""

import json
import hashlib
import re
import glob
import os
import logging
from typing import Dict, List, Set, Optional
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EntityExtractor")

from src.config.config import config
from src.data.data_manager import data_manager
from src.data.postgres import PostgresManager
from src.data.models import Person, Relationship

class EntityService:
    def __init__(self):
        self.persons: Dict[str, Person] = {}
        self.relationships: List[Relationship] = []
        self.name_registry: Dict[str, List[str]] = {}
        self.pg = PostgresManager()  # Connect to Data Lake

    def normalize_name(self, name: str) -> str:
        if not name:
            return ""
        return re.sub(r'\s+', ' ', name.strip().upper())

    def normalize_contact(self, contact: str) -> str:
        if not contact:
            return ""
        return contact.strip().lower()

    def generate_person_id(self, name: str, email: Optional[str] = None, phone: Optional[str] = None) -> str:
        norm_name = self.normalize_name(name)
        primary_contact = ""
        if email and email != "CORREOINVALIDO@PROVEEDORES.COM":
            primary_contact = self.normalize_contact(email)
        elif phone:
            primary_contact = self.normalize_contact(phone)
        composite = f"{norm_name}|{primary_contact}"
        return hashlib.sha256(composite.encode()).hexdigest()[:16]

    def extract_persons_from_suppliers(self, suppliers_file: str):
        logger.info(f"Reading suppliers from: {suppliers_file}")
        data = data_manager.load_latest(suppliers_file)  # Use data_manager
        items = data if isinstance(data, list) else data.get('payload', {}).get('content', [])
        logger.info(f"Found {len(items)} suppliers")
        for supplier in items:
            self._extract_person_from_supplier(supplier)
        logger.info(f"Extracted {len(self.persons)} unique persons")
        logger.info(f"Created {len(self.relationships)} relationships")
        self._report_collisions()

    def _extract_person_from_supplier(self, supplier: Dict):
        name = (supplier.get('contacto') or '').strip()
        if not name:
            return
        email = (supplier.get('correo_contacto') or '').strip()
        phone = (supplier.get('telefono_contacto') or '').strip()
        celular = (supplier.get('celular_contacto') or '').strip()
        position = (supplier.get('posicion_contacto') or '').strip()
        person_id = self.generate_person_id(name, email, phone)
        norm_name = self.normalize_name(name)
        if norm_name not in self.name_registry:
            self.name_registry[norm_name] = []
        self.name_registry[norm_name].append(person_id)
        if person_id not in self.persons:
            self.persons[person_id] = Person(
                person_id=person_id,
                name=name,
                normalized_name=norm_name,
                emails=set(),
                phones=set(),
                positions=set(),
                companies=[]
            )
        person = self.persons[person_id]
        if email and email != "CORREOINVALIDO@PROVEEDORES.COM":
            person.emails.add(email)
        if phone:
            person.phones.add(phone)
        if celular:
            person.phones.add(celular)
        if position:
            person.positions.add(position)
        rpe = supplier.get('rpe')
        razon_social = supplier.get('razon_social')
        if rpe and razon_social:
            person.companies.append({
                'rpe': rpe,
                'razon_social': razon_social,
                'position': position
            })
            self.relationships.append(Relationship(
                person_id=person_id,
                person_name=name,
                rpe=rpe,
                company_name=razon_social,
                relationship_type='REPRESENTATIVE_FOR',
                position=position,
                email=email if email != "CORREOINVALIDO@PROVEEDORES.COM" else None,
                phone=phone or celular
            ))

    def _report_collisions(self):
        collisions = {name: ids for name, ids in self.name_registry.items() if len(ids) > 1}
        if collisions:
            logger.warning(f"Name Collision Resolution: {len(collisions)} names split into {sum(len(ids) for ids in collisions.values())} persons")

    def save_entities(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Convert sets to lists
        persons_export = []
        for person in self.persons.values():
            person_copy = person.dict()
            person_copy['emails'] = list(person_copy['emails'])
            person_copy['phones'] = list(person_copy['phones'])
            person_copy['positions'] = list(person_copy['positions'])
            persons_export.append(person_copy)
        persons_file = f"persons_{timestamp}.json"
        relationships_file = f"relationships_{timestamp}.json"
        
        # 1. Save to JSON (Backup/Legacy)
        data_manager.save_json(persons_export, persons_file)
        data_manager.save_json(self.relationships, relationships_file)
        
        # 2. Sync to Data Lake (Postgres)
        # Convert objects to dicts matching DB schema
        try:
            self.pg.insert_batch(persons_export, 'risk_persons')
            
            # Relationships need dict conversion
            rels_export = [r.dict() for r in self.relationships]
            self.pg.insert_batch(rels_export, 'risk_relationships')
            logger.info("Synced entities to Data Lake (Postgres)")
        except Exception as e:
            logger.error(f"Failed to sync to Data Lake: {e}")

        return persons_file, relationships_file

def main():
    service = EntityService()
    proveedores_files = glob.glob("data/proveedores_*.json")
    if proveedores_files:
        latest_file = max(proveedores_files, key=os.path.getmtime)
        logger.info(f"Using latest file: {latest_file}")
        service.extract_persons_from_suppliers(latest_file)
        service.save_entities()
    else:
        logger.error("No suppliers file found in data/")

if __name__ == "__main__":
    main()
