import os
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Leemos la URL de PostgreSQL desde las variables de entorno de Render
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///cumbre_real.db")

# Render a veces proporciona URLs que empiezan con 'postgres://', 
# pero SQLAlchemy requiere estrictamente 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Creamos el motor de base de datos adecuado para producción
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class RawMaterial(Base):
    __tablename__ = "raw_materials"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    name = Column(String)
    stock_kg = Column(Float, default=0.0)
    cost_per_kg = Column(Float, default=0.0)

class ProductionLot(Base):
    """Lotes de Café Molido Base que regresan del tostador (A granel)"""
    __tablename__ = "production_lots"
    id = Column(Integer, primary_key=True, index=True)
    lot_code = Column(String, unique=True, index=True)
    blend_name = Column(String) 
    total_kg = Column(Float)
    remaining_kg = Column(Float) 
    cost_per_kg = Column(Float)  
    date_created = Column(String)

class ProductPackaged(Base):
    """Producto Final Embolsado listo para la venta en mostrador"""
    __tablename__ = "products_packaged"
    id = Column(Integer, primary_key=True, index=True)
    pack_code = Column(String, unique=True, index=True) 
    name = Column(String)        
    size_label = Column(String)  
    weight_kg = Column(Float)    
    stock_units = Column(Integer)
    cost_per_unit = Column(Float)
    date_packaged = Column(String)

class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String)
    product_name = Column(String)
    pack_source_id = Column(Integer) 
    quantity_sold = Column(Integer)  
    total_income = Column(Float)
    real_cost = Column(Float)        

class SystemLog(Base):
    """Tabla de auditoría global para el funcionamiento del Ctrl + Z Inteligente"""
    __tablename__ = "system_logs"
    id = Column(Integer, primary_key=True, index=True)
    action_type = Column(String, nullable=False)  
    record_id = Column(Integer, nullable=False)    
    details = Column(String, nullable=True)        
    date_created = Column(String)

def init_db():
    Base.metadata.create_all(bind=engine)
