import flet as ft
import sqlite3
import os

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
def get_db_connection():
    data_dir = os.getenv("FLET_APP_STORAGE_DATA", os.getcwd())
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "database.db")
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=DELETE;') 
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS configuracion (id INTEGER PRIMARY KEY, tasa_dia REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS marca (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS producto (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT, 
            marca_id INTEGER, 
            precio REAL, 
            moneda TEXT DEFAULT 'USD',
            FOREIGN KEY(marca_id) REFERENCES marca(id)
        )""")
    if not conn.execute("SELECT count(*) FROM configuracion").fetchone()[0]:
        conn.execute("INSERT INTO configuracion (id, tasa_dia) VALUES (1, 36.50)")
    conn.commit()
    conn.close()

# --- 2. APLICACIÓN PRINCIPAL ---
def main(page: ft.Page):
    init_db()
    page.title = "SOPSoft ERP"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0f0f0f"
    page.padding = ft.Padding(top=45, left=15, right=15, bottom=10)

    tasa_actual = 36.50

    # --- ELEMENTOS DE INTERFAZ ---
    lista_productos = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    lista_marcas = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    text_tasa_header = ft.Text("Cargando...", size=14, weight="bold")
    search_bar = ft.TextField(
        hint_text="Buscar...", 
        prefix_icon=ft.Icons.SEARCH, 
        on_change=lambda _: refrescar_vistas()
    )

    # --- LÓGICA DE DATOS ---
    def obtener_tasa():
        nonlocal tasa_actual
        try:
            conn = get_db_connection()
            tasa_row = conn.execute("SELECT tasa_dia FROM configuracion WHERE id=1").fetchone()
            tasa_actual = float(tasa_row['tasa_dia']) if tasa_row else 36.50
            conn.close()
        except: tasa_actual = 36.50
        text_tasa_header.value = f"Tasa: {tasa_actual} Bs"
        page.update()

    def refrescar_vistas():
        lista_productos.controls.clear()
        lista_marcas.controls.clear()
        conn = get_db_connection()
        
        search_val = f"%{search_bar.value}%"
        prods = conn.execute("""
            SELECT p.id, p.nombre, m.nombre AS marca_nom, p.marca_id, p.precio, p.moneda 
            FROM producto p LEFT JOIN marca m ON p.marca_id = m.id 
            WHERE p.nombre LIKE ? OR m.nombre LIKE ? ORDER BY p.id DESC
        """, (search_val, search_val)).fetchall()

        for p in prods:
            v_usd = p['precio'] if p['moneda'] == "USD" else p['precio'] / tasa_actual
            v_bs = p['precio'] * tasa_actual if p['moneda'] == "USD" else p['precio']
            
            lista_productos.controls.append(ft.Container(
                content=ft.Row([
                    ft.Column([ft.Text(p['nombre'], weight="bold"), ft.Text(p['marca_nom'] or "Sin Marca", size=11, color="grey")], expand=True),
                    ft.Column([ft.Text(f"${v_usd:.2f}", color="green"), ft.Text(f"{v_bs:.2f} Bs", size=10, color="amber")], horizontal_alignment="end"),
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda _, x=p: abrir_editar_prod(x)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", on_click=lambda _, x=p: confirmar_eliminar("producto", x['id'], x['nombre']))
                ]), padding=12, bgcolor="#1a1a1a", border_radius=10
            ))

        marcas = conn.execute("SELECT * FROM marca ORDER BY nombre ASC").fetchall()
        dd_marca.options = [ft.dropdown.Option(key=str(m['id']), text=m['nombre']) for m in marcas]
        dd_marca_aumento.options = [ft.dropdown.Option(key="todas", text="Todas las marcas")] + [ft.dropdown.Option(key=str(m['id']), text=m['nombre']) for m in marcas]
        
        for m in marcas:
            lista_marcas.controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.SELL_ROUNDED, color="amber", size=20),
                    ft.Text(m['nombre'], weight="bold", expand=True),
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda _, x=m: abrir_editar_marca(x)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", on_click=lambda _, x=m: confirmar_eliminar("marca", x['id'], x['nombre']))
                ]), padding=12, bgcolor="#1a1a1a", border_radius=10
            ))
        conn.close()
        page.update()

    # --- MODALES Y DIÁLOGOS ---
    def cerrar_modales(e):
        modal_tasa.open = modal_marca.open = modal_producto.open = modal_confirm.open = modal_aumento.open = False
        page.update()

    # Modal Confirmación de Eliminación
    item_a_eliminar = {"tabla": "", "id": None}
    def confirmar_eliminar(tabla, id_item, nombre):
        item_a_eliminar["tabla"] = tabla
        item_a_eliminar["id"] = id_item
        text_confirm.value = f"¿Estás seguro de eliminar '{nombre}'?"
        modal_confirm.open = True
        page.update()

    def ejecutar_eliminacion(e):
        conn = get_db_connection()
        conn.execute(f"DELETE FROM {item_a_eliminar['tabla']} WHERE id=?", (item_a_eliminar['id'],))
        conn.commit(); conn.close()
        cerrar_modales(None)
        refrescar_vistas()

    text_confirm = ft.Text("")
    modal_confirm = ft.AlertDialog(
        title=ft.Text("Confirmar"),
        content=text_confirm,
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar_modales),
            ft.FilledButton("Eliminar", bgcolor="red", on_click=ejecutar_eliminacion)
        ]
    )

    # Teclado numérico para la Tasa
    txt_nueva_tasa = ft.TextField(label="Precio Dólar", keyboard_type=ft.KeyboardType.NUMBER)
    modal_tasa = ft.AlertDialog(title=ft.Text("Tasa"), content=txt_nueva_tasa, actions=[ft.FilledButton("Guardar", on_click=lambda _: guardar_tasa())])
    
    txt_nombre_marca = ft.TextField(label="Nombre Marca", capitalization=ft.TextCapitalization.WORDS)
    edit_marca_id = ft.Text("")
    modal_marca = ft.AlertDialog(title=ft.Text("Marca"), content=txt_nombre_marca, actions=[ft.FilledButton("Guardar", on_click=lambda _: guardar_marca())])

    # Teclado numérico para el Precio del Producto
    txt_p_nom = ft.TextField(label="Producto", capitalization=ft.TextCapitalization.SENTENCES)
    dd_marca = ft.Dropdown(label="Marca")
    txt_p_pre = ft.TextField(label="Precio", keyboard_type=ft.KeyboardType.NUMBER)
    rb_moneda = ft.RadioGroup(content=ft.Row([ft.Radio(value="USD", label="$"), ft.Radio(value="BS", label="Bs")]), value="USD")
    edit_prod_id = ft.Text("")
    modal_producto = ft.AlertDialog(
        title=ft.Text("Producto"), 
        content=ft.Column([txt_p_nom, dd_marca, rb_moneda, txt_p_pre], tight=True), 
        actions=[ft.FilledButton("Guardar", on_click=lambda _: guardar_producto())]
    )

    # Modal Aumento Masivo
    dd_marca_aumento = ft.Dropdown(label="Marca", value="todas")
    txt_valor_aumento = ft.TextField(label="Monto/Porcentaje", keyboard_type=ft.KeyboardType.NUMBER)
    rb_tipo_aumento = ft.RadioGroup(content=ft.Row([ft.Radio(value="fijo", label="Fijo"), ft.Radio(value="porc", label="%")]), value="fijo")
    rb_moneda_aumento = ft.RadioGroup(content=ft.Row([ft.Radio(value="USD", label="$"), ft.Radio(value="BS", label="Bs")]), value="USD")

    def ejecutar_aumento_masivo(e):
        if not txt_valor_aumento.value: return
        try:
            valor = float(txt_valor_aumento.value.replace(",", "."))
            conn = get_db_connection()
            if rb_tipo_aumento.value == "fijo":
                if rb_moneda_aumento.value == "BS":
                    query = f"UPDATE producto SET precio = CASE WHEN moneda = 'USD' THEN precio + ({valor}/{tasa_actual}) ELSE precio + {valor} END"
                else:
                    query = f"UPDATE producto SET precio = CASE WHEN moneda = 'BS' THEN precio + ({valor}*{tasa_actual}) ELSE precio + {valor} END"
            else:
                query = f"UPDATE producto SET precio = precio * (1 + {valor}/100)"
            
            if dd_marca_aumento.value != "todas":
                conn.execute(query + " WHERE marca_id=?", (dd_marca_aumento.value,))
            else: conn.execute(query)
            conn.commit(); conn.close(); cerrar_modales(None); refrescar_vistas()
        except: pass

    modal_aumento = ft.AlertDialog(
        title=ft.Text("Aumento Masivo"), 
        content=ft.Column([dd_marca_aumento, rb_tipo_aumento, rb_moneda_aumento, txt_valor_aumento], tight=True),
        actions=[ft.TextButton("Cancelar", on_click=cerrar_modales), ft.FilledButton("Aplicar", on_click=ejecutar_aumento_masivo)]
    )

    # --- FUNCIONES DB ---
    def guardar_tasa():
        conn = get_db_connection(); conn.execute("UPDATE configuracion SET tasa_dia=? WHERE id=1", (float(txt_nueva_tasa.value.replace(",", ".")),))
        conn.commit(); conn.close(); obtener_tasa(); cerrar_modales(None); refrescar_vistas()

    def guardar_marca():
        conn = get_db_connection()
        if edit_marca_id.value: conn.execute("UPDATE marca SET nombre=? WHERE id=?", (txt_nombre_marca.value, edit_marca_id.value))
        else: conn.execute("INSERT INTO marca (nombre) VALUES (?)", (txt_nombre_marca.value,))
        conn.commit(); conn.close(); cerrar_modales(None); refrescar_vistas()

    def guardar_producto():
        conn = get_db_connection()
        pre = float(txt_p_pre.value.replace(",", "."))
        if edit_prod_id.value: conn.execute("UPDATE producto SET nombre=?, marca_id=?, precio=?, moneda=? WHERE id=?", (txt_p_nom.value, dd_marca.value, pre, rb_moneda.value, edit_prod_id.value))
        else: conn.execute("INSERT INTO producto (nombre, marca_id, precio, moneda) VALUES (?, ?, ?, ?)", (txt_p_nom.value, dd_marca.value, pre, rb_moneda.value))
        conn.commit(); conn.close(); cerrar_modales(None); refrescar_vistas()

    def abrir_editar_prod(p):
        edit_prod_id.value = str(p['id']); txt_p_nom.value = p['nombre']; dd_marca.value = str(p['marca_id']); txt_p_pre.value = str(p['precio']); rb_moneda.value = p['moneda']
        modal_producto.open = True; page.update()

    def abrir_editar_marca(m):
        edit_marca_id.value = str(m['id']); txt_nombre_marca.value = m['nombre']
        modal_marca.open = True; page.update()

    # --- ESTRUCTURA TABS ---
    header = ft.Row([
        ft.Text("SOPSoft ERP", size=22, weight="bold"),
        ft.Row([
            ft.IconButton(ft.Icons.TRENDING_UP, icon_color="greenaccent", on_click=lambda _: setattr(modal_aumento, "open", True) or page.update()),
            ft.Container(content=text_tasa_header, padding=10, bgcolor="blue900", border_radius=8, on_click=lambda _: setattr(modal_tasa, "open", True) or page.update())
        ])
    ], alignment="spaceBetween")

    main_tabs = ft.Tabs(
        selected_index=0, expand=True,
        length=2,
        content=ft.Column(expand=True, controls=[
            ft.TabBar(tabs=[ft.Tab(label="Productos", icon=ft.Icons.SHOPPING_BAG), ft.Tab(label="Marcas", icon=ft.Icons.SELL)]),
            ft.TabBarView(expand=True, controls=[
                ft.Column([search_bar, lista_productos], expand=True),
                ft.Column([lista_marcas], expand=True)
            ])
        ])
    )

    page.floating_action_button = ft.FloatingActionButton(icon=ft.Icons.ADD, on_click=lambda _: abrir_nuevo_segun_tab())

    def abrir_nuevo_segun_tab():
        if main_tabs.selected_index == 0:
            edit_prod_id.value = ""; txt_p_nom.value = ""; txt_p_pre.value = ""; dd_marca.value = None; modal_producto.open = True
        else:
            edit_marca_id.value = ""; txt_nombre_marca.value = ""; modal_marca.open = True
        page.update()

    page.overlay.extend([modal_tasa, modal_marca, modal_producto, modal_confirm, modal_aumento])
    page.add(header, ft.Divider(height=10, color="transparent"), main_tabs)
    
    obtener_tasa(); refrescar_vistas()

if __name__ == "__main__":
    ft.app(target=main)