from models import SessionLocal, RawMaterial

def registrar_entrada_materia_prima(codigo, nombre, kilos_nuevos, costo_kilo):
    """
    Suma kilos al stock si el café ya existe, o crea uno nuevo con su costo actual.
    """
    session = SessionLocal()
    try:
        materia = session.query(RawMaterial).filter(RawMaterial.code == codigo).first()

        if materia:
            materia.stock_kg += kilos_nuevos
            materia.cost_per_kg = costo_kilo  
            mensaje = f" 📥 Stock actualizado: {nombre}. Nuevo inventario: {materia.stock_kg:.2f} kg."
        else:
            materia = RawMaterial(
                code=codigo,
                name=nombre,
                stock_kg=kilos_nuevos,
                cost_per_kg=costo_kilo
            )
            session.add(materia)
            mensaje = f" ✨ Nuevo café registrado: {nombre} ({codigo}) con {kilos_nuevos:.2f} kg."

        session.commit()
        return {"status": "success", "message": mensaje}

    except Exception as e:
        session.rollback()
        return {"status": "error", "message": f"Error en inventario: {str(e)}"}
    finally:
        session.close()
