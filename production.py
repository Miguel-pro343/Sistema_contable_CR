from models import SessionLocal, RawMaterial, ProductionLot, ProductPackaged, SystemLog
from datetime import datetime

def transformar_materia_a_procesado(lot_code, blend_name, total_kg, tipo_proceso, cod_arabica, kg_arabica, cod_robusta, kg_robusta, costo_tueste=0.0, costo_transporte=0.0, fecha_manual=None):
    session = SessionLocal()
    try:
        lote_existente = session.query(ProductionLot).filter(ProductionLot.lot_code == lot_code).first()
        if lote_existente:
            return {
                "status": "error",
                "message": f" ❌ El código de tolva '{lot_code}' ya existe. Usa un código diferente."
            }
            
        kg_arabica = float(kg_arabica or 0.0)
        kg_robusta = float(kg_robusta or 0.0)
        total_kg = float(total_kg or 0.0)
        costo_tueste = float(costo_tueste or 0.0)
        costo_transporte = float(costo_transporte or 0.0)
        
        if total_kg <= 0:
            return {"status": "error", "message": " ❌ Los kilos finales obtenidos deben ser mayores a 0."}
        if kg_arabica == 0 and kg_robusta == 0:
            return {"status": "error", "message": " ❌ Debes ingresar los kilos sacados de al menos un costal."}
            
        costo_materia_prima = 0.0

        if kg_arabica > 0:
            mat_a = session.query(RawMaterial).filter(RawMaterial.code == cod_arabica).first()
            if not mat_a:
                return {"status": "error", "message": f" ❌ No se encontró el café Arábica: {cod_arabica}"}
            if mat_a.stock_kg < kg_arabica:
                return {"status": "error", "message": f" ❌ Stock insuficiente en Arábica ({cod_arabica}). Disponible: {mat_a.stock_kg:.2f} kg"}

            costo_materia_prima += kg_arabica * float(mat_a.cost_per_kg)
            mat_a.stock_kg -= kg_arabica

        if kg_robusta > 0:
            mat_r = session.query(RawMaterial).filter(RawMaterial.code == cod_robusta).first()
            if not mat_r:
                return {"status": "error", "message": f" ❌ No se encontró el café Robusta: {cod_robusta}"}
            if mat_r.stock_kg < kg_robusta:
                return {"status": "error", "message": f" ❌ Stock insuficiente en Robusta ({cod_robusta}). Disponible: {mat_r.stock_kg:.2f} kg"}

            costo_materia_prima += kg_robusta * float(mat_r.cost_per_kg)
            mat_r.stock_kg -= kg_robusta

        costo_total_tanda = costo_materia_prima + costo_tueste + costo_transporte
        costo_por_kg_obtenido = costo_total_tanda / total_kg
        fecha_final = fecha_manual if fecha_manual else datetime.now().strftime("%Y-%m-%d %H:%M")

        nuevo_lote = ProductionLot(
            lot_code=lot_code,
            blend_name=f"{blend_name} | Usado: {cod_arabica}({kg_arabica}kg) y {cod_robusta}({kg_robusta}kg)",
            total_kg=total_kg,
            remaining_kg=total_kg,
            cost_per_kg=round(costo_por_kg_obtenido, 2),
            date_created=fecha_final
        )
        session.add(nuevo_lote)
        session.flush()  
        
        log_operacion = SystemLog(action_type="TRANSFORMACION", record_id=nuevo_lote.id)
        session.add(log_operacion)

        session.commit()
        return {
            "status": "success",
            "message": f" 🎉 Lote {lot_code} creado. Costo MP: ${costo_materia_prima:.2f}. Costo por kilo limpio: ${costo_por_kg_obtenido:.2f}/kg."
        }
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": f"Error en producción: {str(e)}"}
    finally:
        session.close()

def empaquetar_y_crear_blend(pack_code, name, size_label, stock_units, tolva_a_id, kg_a, tolva_b_id=None, kg_b=0.0, costo_bolsa=0.0, costo_flete=0.0, fecha_manual=None):
    session = SessionLocal()
    try:
        empaque_existente = session.query(ProductPackaged).filter(ProductPackaged.pack_code == pack_code).first()
        if empaque_existente:
            return {"status": "error", "message": f" ❌ El código de lote comercial '{pack_code}' ya existe. Elige otro."}
            
        if size_label == "1 kg":
            peso_unitario = 1.0
        elif size_label == "250g":
            peso_unitario = 0.25
        else:
            peso_unitario = 0.50  

        peso_total_requerido = float(stock_units) * peso_unitario
        peso_declarado_usuario = float(kg_a or 0.0) + float(kg_b or 0.0)

        if abs(peso_total_requerido - peso_declarado_usuario) > 0.01:
            return {
                "status": "error",
                "message": f" ⚖️ Desbalance: Requieres extraer {peso_total_requerido:.2f} kg de las tolvas para armar esas bolsas. Tu mezcla suma {peso_declarado_usuario:.2f} kg."
            }
            
        costo_acumulado_cafe = 0.0
        
        t_a = session.query(ProductionLot).filter(ProductionLot.id == tolva_a_id).first()
        if t_a.remaining_kg < kg_a:
            return {"status": "error", "message": f" ❌ Inventario insuficiente en la tolva {t_a.lot_code}. Disponible: {t_a.remaining_kg:.2f} kg"}
        t_a.remaining_kg -= kg_a
        costo_acumulado_cafe += kg_a * t_a.cost_per_kg

        if tolva_b_id and kg_b > 0:
            t_b = session.query(ProductionLot).filter(ProductionLot.id == tolva_b_id).first()
            if t_b.remaining_kg < kg_b:
                return {"status": "error", "message": f" ❌ Inventario insuficiente en la tolva secundaria {t_b.lot_code}. Disponible: {t_b.remaining_kg:.2f} kg"}
            t_b.remaining_kg -= kg_b
            costo_acumulado_cafe += kg_b * t_b.cost_per_kg
            
        costo_unitario_bolsa = (costo_acumulado_cafe / float(stock_units)) + float(costo_bolsa or 0.0) + float(costo_flete or 0.0)
        fecha_final = fecha_manual if fecha_manual else datetime.now().strftime("%Y-%m-%d %H:%M")

        nuevo_empaque = ProductPackaged(
            pack_code=pack_code,
            name=name,
            size_label=size_label,
            weight_kg=peso_unitario, 
            stock_units=stock_units,
            cost_per_unit=round(costo_unitario_bolsa, 2),
            date_packaged=fecha_final
        )
        session.add(nuevo_empaque)
        session.flush()
        
        detalles_respaldo = f"{tolva_a_id}({kg_a}kg)" + (f" y {tolva_b_id}({kg_b}kg)" if (tolva_b_id and kg_b > 0) else "")
        log_operacion = SystemLog(action_type="EMPAQUE", record_id=nuevo_empaque.id, details=detalles_respaldo)
        session.add(log_operacion)
        
        session.commit()
        return {"status": "success", "message": f" 📦 ¡Lote {pack_code} ({size_label}) registrado con éxito e inventario de tolvas actualizado!"}
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": f"Error al empacar: {str(e)}"}
    finally:
        session.close()

def deshacer_ultima_operacion_global():
    session = SessionLocal()
    try:
        ultimo_log = session.query(SystemLog).order_by(SystemLog.id.desc()).first()
        if not ultimo_log:
            return {"status": "warning", "message": " ⚠️ No hay ninguna operación en el historial reciente para deshacer."}
            
        if ultimo_log.action_type == "TRANSFORMACION":
            lote = session.query(ProductionLot).filter(ProductionLot.id == ultimo_log.record_id).first()
            if not lote:
                session.delete(ultimo_log)
                session.commit()
                return {"status": "error", "message": " ❌ El lote de producción ya no se encuentra en la base de datos."}
            if lote.remaining_kg < lote.total_kg:
                return {
                    "status": "error",
                    "message": f" ❌ No se puede deshacer. Ya extrajiste café de la tolva '{lote.lot_code}' en la Mesa de Blends."
                }
            lote_codigo = lote.lot_code
            descripcion = lote.blend_name
            try:
                if "Usado:" in descripcion:
                    partes = descripcion.split("Usado:")[1].split(" y ")
                    part_a = partes[0].strip()
                    cod_a = part_a.split("(")[0]
                    kg_a = float(part_a.split("(")[1].replace("kg)", ""))

                    part_r = partes[1].strip()
                    cod_r = part_r.split("(")[0]
                    kg_r = float(part_r.split("(")[1].replace("kg)", ""))
                    
                    if kg_a > 0:
                        mat_a = session.query(RawMaterial).filter(RawMaterial.code == cod_a).first()
                        if mat_a: mat_a.stock_kg += kg_a
                    if kg_r > 0:
                        mat_r = session.query(RawMaterial).filter(RawMaterial.code == cod_r).first()
                        if mat_r: mat_r.stock_kg += kg_r
            except Exception:
                pass
            session.delete(lote)
            msg = f" 🔄 ¡Ctrl+Z Exitoso! Se eliminó el tueste bruto '{lote_codigo}' de las tolvas y los kilos regresaron a sus costales de café verde en bodega."

        elif ultimo_log.action_type == "EMPAQUE":
            empaque = session.query(ProductPackaged).filter(ProductPackaged.id == ultimo_log.record_id).first()
            if not empaque:
                session.delete(ultimo_log)
                session.commit()
                return {"status": "error", "message": " ❌ El registro de producto empacado ya no existe."}
            pack_codigo = empaque.pack_code
            try:
                if ultimo_log.details:
                    partes = ultimo_log.details.split(" y ")
                    for parte in partes:
                        t_id = int(parte.split("(")[0])
                        t_kg = float(parte.split("(")[1].replace("kg)", ""))

                        tolva_origen = session.query(ProductionLot).filter(ProductionLot.id == t_id).first()
                        if tolva_origen:
                            tolva_origen.remaining_kg += t_kg
            except Exception as e:
                return {"status": "error", "message": f" ❌ Error regresando el café molido a las tolvas: {str(e)}"}
            session.delete(empaque)
            msg = f" 🔄 ¡Ctrl+Z Exitoso! Se eliminó el lote comercial '{pack_codigo}' del anaquel y los kilos de café molido regresaron a sus respectivas tolvas."

        session.delete(ultimo_log)
        session.commit()
        return {"status": "success", "message": msg}
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": f"Error al ejecutar Ctrl+Z global: {str(e)}"}
    finally:
        session.close()
