from sqlalchemy import inspect
from app.db.base import Base

def get_live_schema_context() -> str:
    """
    Senior Utility: Automatically extracts the database schema from SQLAlchemy models.
    Ensures ZERO hardcoding of table/column names in AI prompts.
    """
    schema_parts = []
    
    # Iterate through all models registered in Base
    for table_name, table in Base.metadata.tables.items():
        columns = []
        for column in table.columns:
            # Extract column name, type, and any comments/constraints
            col_info = f"{column.name} ({column.type})"
            if column.primary_key:
                col_info += " [PRIMARY KEY]"
            if column.foreign_keys:
                # Show where it points to for better AI join logic
                fk = list(column.foreign_keys)[0]
                col_info += f" [FK -> {fk.column.table.name}.{fk.column.name}]"
            columns.append(col_info)
        
        table_str = f"Table: {table_name}\nColumns: {', '.join(columns)}"
        schema_parts.append(table_str)
        
    return "\n\n".join(schema_parts)
