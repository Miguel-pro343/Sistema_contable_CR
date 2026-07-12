import streamlit as st
import pandas as pd
from datetime import datetime
from models import init_db, SessionLocal, RawMaterial, ProductionLot, ProductPackaged, Sale
from inventory import registrar_entrada_materia_prima
from production import transformar_materia_a_procesado, empaquetar_y_crear_blend, deshacer_ultima_operacion_global
from sales_blends import registrar_venta_por_bolsa

# 📊 CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Cumbre Real - Control de Inventarios", layout="wide", page_icon="☕")

# Inicializar las tablas en la base de datos de la nube si no existen
try:
    init_db()
except Exception as e:
    st.error(f"⚠️ Error de conexión a la base de datos: {e}")

st.title("☕ Cumbre Real - Sistema de Inventario y Costos")
st.subheader("Control centralizado en la nube para múltiples dispositivos")
st.write("---")

# ==========================================
# 📊 SECCIÓN 1: VISTA GENERAL DE INVENTARIOS
# ==========================================
st.header("📈 Estado Actual del Negocio")
col1, col2, col3 = st.columns(3)

session = SessionLocal()
try:
    # Obtener datos frescos de las tablas
    raw_data = session.query(RawMaterial).all()
    lots_data = session.query(ProductionLot).all()
    pack_data = session.query(ProductPackaged).all()
    sales_data = session.query(Sale).order_by(Sale.id.desc()).all()

    # Mostrar métricas resumidas
    with col1:
        st.metric(label="Variedades de Café Verde (Sacos/Bodega)", value=f"{len(raw_data)} tipos")
    with col2:
        st.metric(label="Lotes Brutos en Tolvas (A Granel)", value=f"{len([l for l in lots_data if l.remaining_kg > 0])} activos")
    with col3:
        st.metric(label="Bolsas Disponibles en Anaquel", value=f"{sum(p.stock_units for p in pack_data)} unidades")

    # Mostrar Tablas Detalladas
    tabs = st.tabs(["🌾 Café Verde en Bodega", "🏭 Café en Tolvas (Molienda)", "📦 Bolsas Listas para Venta", "💰 Historial de Ventas"])
    
    with tabs[0]:
        if raw_data:
            df_raw = pd.DataFrame([{
                "Código": r.code, "Nombre": r.name, "Stock (kg)": f"{r.stock_kg:.2f} kg", "Último Costo/kg": f"${r.cost_per_kg:.2f}"
            } for r in raw_data])
            st.dataframe(df_raw, use_container_width=True)
        else:
            st.info("No hay café verde registrado en bodega.")

    with tabs[1]:
        if lots_data:
            df_lots = pd.DataFrame([{
                "Tolva ID": l.id, "Código Lote": l.lot_code, "Descripción de Mezcla": l.blend_name, 
                "Kilos Totales": f"{l.total_kg:.2f} kg", "Kilos Disponibles": f"{l.remaining_kg:.2f} kg", "Costo Real/kg": f"${l.cost_per_kg:.2f}"
            } for l in lots_data])
            st.dataframe(df_lots, use_container_width=True)
        else:
            st.info("No hay lotes procesados en tolvas actualmente.")

    with tabs[2]:
        if pack_data:
            df_pack = pd.DataFrame([{
                "Código Comercial": p.pack_code, "Nombre Producto": p.name, "Presentación": p.size_label, 
                "Bolsas en Stock": f"{p.stock_units} uds", "Costo Final/Unidad": f"${p.cost_per_unit:.2f}"
            } for p in pack_data])
            st.dataframe(df_pack, use_container_width=True)
        else:
            st.info("No hay producto embolsado en anaqueles.")

    with tabs[3]:
        if sales_data:
            df_sales = pd.DataFrame([{
                "Fecha": s.date, "Producto": s.product_name, "Unidades": s.quantity_sold, 
                "Total Cobrado": f"${s.total_income:.2f}", "Costo de Insumos": f"${s.real_cost:.2f}",
                "Ganancia Real": f"${(s.total_income - s.real_cost):.2f}"
            } for s in sales_data])
            st.dataframe(df_sales, use_container_width=True)
        else:
            st.info("Aún no se han registrado ventas en el sistema.")

finally:
    session.close()

st.write("---")

# ==========================================
# 🛠️ SECCIÓN 2: ACCIONES Y OPERACIONES
# ==========================================
st.header("⚡ Panel de Operaciones en Tiempo Real")
opciones_modulo = st.selectbox("Selecciona la acción que vas a realizar:", [
    "📥 Registrar Entrada de Café Verde",
    "🏭 Registrar Tueste (Materia Prima -> Tolva)",
    "📦 Registrar Embolsado (Meza de Blends -> Anaquel)",
    "💰 Registrar Venta de Mostrador",
    "🔄 Control Z (Deshacer Último Error)"
])

# ---- MODULO 1: ENTRADA MATERIA PRIMA ----
if opciones_modulo == "📥 Registrar Entrada de Café Verde":
    st.subheader("📥 Entrada de Café Verde a Bodega")
    with st.form("form_materia_prima"):
        c1, c2 = st.columns(2)
        with c1:
            cod = st.text_input("Código de Variedad (Ej: AR-001, RB-002):").strip().upper()
            nom = st.text_input("Nombre comercial del café (Ej: Pergamino Puebla, Robusta Veracruz):")
        with c2:
            kg = st.number_input("Kilos Nuevos:", min_value=0.0, step=0.1)
            costo = st.number_input("Costo por Kilo ($):", min_value=0.0, step=0.1)
        
        btn = st.form_submit_button("Guardar en Bodega")
        if btn:
            if cod and nom and kg > 0 and costo > 0:
                res = registrar_entrada_materia_prima(cod, nom, kg, costo)
                if res["status"] == "success": st.success(res["message"])
                else: st.error(res["message"])
                st.rerun()
            else:
                st.warning("Por favor rellena todos los campos con valores mayores a cero.")

# ---- MODULO 2: TUESTE / TRANSFORMACIÓN ----
elif opciones_modulo == "🏭 Registrar Tueste (Materia Prima -> Tolva)":
    st.subheader("🏭 Salida de Tostador a Tolva Bruta")
    
    # Cargar selectores dinámicos
    session = SessionLocal()
    opciones_materia = [f"{r.code} | {r.name} (Disp: {r.stock_kg:.2f}kg)" for r in session.query(RawMaterial).all()]
    session.close()

    if not opciones_materia:
        st.warning("⚠️ Primero debes registrar café verde en bodega para poder tostar.")
    else:
        with st.form("form_tueste"):
            c1, c2, c3 = st.columns(3)
            with c1:
                lot_code = st.text_input("Código Único de Tolva (Ej: TLV-A1):").strip().upper()
                blend_name = st.text_input("Nombre del Lote (Ej: Base Arábica Oscuro):")
                total_kg = st.number_input("Kilos Limpios Obtenidos (Final):", min_value=0.0, step=0.1)
            with c2:
                sel_a = st.selectbox("Café Arábica Utilizado:", opciones_materia)
                kg_a = st.number_input("Kilos Sacados de Arábica:", min_value=0.0, step=0.1)
                costo_t = st.number_input("Costo de Maquila/Tueste total ($):", min_value=0.0, step=1.0)
            with c3:
                sel_r = st.selectbox("Café Robusta Utilizado (Opcional):", ["NINGUNO"] + opciones_materia)
                kg_r = st.number_input("Kilos Sacados de Robusta:", min_value=0.0, step=0.1)
                costo_f = st.number_input("Costo de Transporte/Flete total ($):", min_value=0.0, step=1.0)
            
            f_manual = st.text_input("Fecha/Hora Manual (Vacío para automática YYYY-MM-DD HH:MM):")
            btn_t = st.form_submit_button("Procesar Tueste y Absorber Mermas")

            if btn_t:
                cod_a = sel_a.split(" | ")[0]
                cod_r = None if sel_r == "NINGUNO" else sel_r.split(" | ")[0]
                
                res = transformar_materia_a_procesado(
                    lot_code, blend_name, total_kg, "TUESTE", 
                    cod_a, kg_a, cod_r, kg_r, costo_t, costo_f, f_manual if f_manual else None
                )
                if res["status"] == "success": st.success(res["message"])
                else: st.error(res["message"])
                st.rerun()

# ---- MODULO 3: EMBOLSADO Y MEZCLADO ----
elif opciones_modulo == "📦 Registrar Embolsado (Meza de Blends -> Anaquel)":
    st.subheader("📦 Empaque Comercial y Armado de Blends")
    
    session = SessionLocal()
    opciones_tolvas = [f"{l.id} | Tolva: {l.lot_code} - {l.blend_name} (Disp: {l.remaining_kg:.2f}kg)" for l in session.query(ProductionLot).filter(ProductionLot.remaining_kg > 0).all()]
    session.close()

    if not opciones_tolvas:
        st.warning("⚠️ No hay café disponible en las tolvas. Debes registrar un tueste primero.")
    else:
        with st.form("form_empaque"):
            c1, c2 = st.columns(2)
            with c1:
                pack_code = st.text_input("Código de Lote Comercial (Ej: LOTE-01):").strip().upper()
                name = st.text_input("Nombre del Producto en Bolsa (Ej: Café Gourmet Cumbre):")
                size_label = st.selectbox("Presentación de la Bolsa:", ["1 kg", "500g", "250g"])
                stock_units = st.number_input("Cantidad de bolsas a armar:", min_value=1, step=1)
            with c2:
                sel_ta = st.selectbox("Tolva Principal (Origen A):", opciones_tolvas)
                kg_ta = st.number_input("Kilos a extraer de Tolva A:", min_value=0.0, step=0.01)
                
                sel_tb = st.selectbox("Tolva Secundaria (Origen B - Opcional):", ["NINGUNA"] + opciones_tolvas)
                kg_tb = st.number_input("Kilos a extraer de Tolva B:", min_value=0.0, step=0.01)
                
                c_bolsa = st.number_input("Costo Unitario de Insumos (Bolsa + Válvula) $:", min_value=0.0, step=0.1)
                c_flete = st.number_input("Costo de Flete distribuido por unidad $:", min_value=0.0, step=0.1)
                
            f_manual = st.text_input("Fecha/Hora Manual (Vacío para automática):")
            btn_e = st.form_submit_button("Armar Bolsas y Calcular Costo Unitario Exacto")

            if btn_e:
                id_ta = int(sel_ta.split(" | ")[0])
                id_tb = None if sel_tb == "NINGUNA" else int(sel_tb.split(" | ")[0])
                
                res = empaquetar_y_crear_blend(
                    pack_code, name, size_label, stock_units, id_ta, kg_ta, id_tb, kg_tb, c_bolsa, c_flete, f_manual if f_manual else None
                )
                if res["status"] == "success": st.success(res["message"])
                else: st.error(res["message"])
                st.rerun()

# ---- MODULO 4: VENTAS POR BOLSA ----
elif opciones_modulo == "💰 Registrar Venta de Mostrador":
    st.subheader("💰 Registro Rápido de Ventas")
    
    session = SessionLocal()
    opciones_productos = [f"{p.pack_code} | {p.name} ({p.size_label}) - Disp: {p.stock_units} uds" for p in session.query(ProductPackaged).filter(ProductPackaged.stock_units > 0).all()]
    session.close()

    if not opciones_productos:
        st.warning("⚠️ No tienes bolsas de café en anaquel disponibles para vender.")
    else:
        with st.form("form_ventas"):
            sel_prod = st.selectbox("Selecciona el lote comercial vendido:", opciones_productos)
            uds = st.number_input("Unidades vendidas:", min_value=1, step=1)
            total = st.number_input("Total cobrado al cliente ($):", min_value=0.0, step=1.0)
            f_manual = st.text_input("Fecha/Hora Manual (Vacío para tiempo real):")
            
            btn_v = st.form_submit_button("Concluir Venta")
            if btn_v:
                p_code = sel_prod.split(" | ")[0]
                res = registrar_venta_por_bolsa(p_code, uds, total, f_manual if f_manual else None)
                if res["status"] == "success": st.success(res["message"])
                else: st.error(res["message"])
                st.rerun()

# ---- MODULO 5: CONTROL + Z ----
elif opciones_modulo == "🔄 Control Z (Deshacer Último Error)":
    st.subheader("🔄 Reversión Segura e Inteligente")
    st.write("¿Hubo una confusión de kilos o te equivocaste de código? El sistema puede revertir los inventarios de forma inteligente.")
    
    btn_z = st.button("🚨 DESHACER ÚLTIMA OPERACIÓN REGISTRADA")
    if btn_z:
        res = deshacer_ultima_operacion_global()
        if res["status"] == "success": st.success(res["message"])
        elif res["status"] == "warning": st.warning(res["message"])
        else: st.error(res["message"])
        st.rerun()
