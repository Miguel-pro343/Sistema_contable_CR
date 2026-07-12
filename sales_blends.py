from models import SessionLocal, ProductPackaged, Sale
from datetime import datetime

def registrar_venta_por_bolsa(pack_code, unidades_vendidas, total_cobrado, fecha_manual=None):
    session = SessionLocal()
    try:
        producto = session.query(ProductPackaged).filter(ProductPackaged.pack_code == pack_code).first()
        if not producto:
            return {"status": "error", "message": " ❌ No se encontró el producto."}

        if producto.stock_units < unidades_vendidas:
            return {"status": "error", "message": f" ⚠️ Stock insuficiente. Solo quedan {producto.stock_units} unidades."}

        costo_real_total = producto.cost_per_unit * unidades_vendidas
        producto.stock_units -= unidades_vendidas
        fecha_final = fecha_manual if fecha_manual else datetime.now().strftime("%Y-%m-%d %H:%M")

        nueva_venta = Sale(
            product_name=f"{producto.name} ({producto.size_label})",
            quantity_sold=unidades_vendidas,
            total_income=total_cobrado,
            real_cost=round(costo_real_total, 2),
            date=fecha_final
        )
        session.add(nueva_venta)
        session.commit()
        return {"status": "success", "message": f" 💰 Venta registrada con éxito. Fecha asignada: {fecha_final}"}
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()
