import sys
import os
import logging
from sqlalchemy import create_engine, inspect

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add backend to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append(backend_path)

from app.core.config import settings

def check_constraints():
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    
    for table in ["user_metadata", "groups"]:
        print(f"\n--- Checking table: {table} ---")
        unique_constraints = inspector.get_unique_constraints(table)
        pk_constraint = inspector.get_pk_constraint(table)
        indexes = inspector.get_indexes(table)
        
        print(f"PK Constraint: {pk_constraint}")
        
        print("Unique Constraints:")
        for uc in unique_constraints:
            print(f" - {uc['name']}: {uc['column_names']}")
            
        print("Indexes:")
        for idx in indexes:
            print(f" - {idx['name']}: {idx['column_names']} (Unique: {idx['unique']})")

if __name__ == "__main__":
    check_constraints()
