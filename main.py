import flet as ft
import sqlite3
import os

# --- 1. CONFIGURACIÓN DE BASE DE DATOS (COMPATIBLE CON ANDROID) ---
def get_db_connection():
    # En Android, os.getcwd() es de solo lectura. 
    # Usamos FLET_APP_STORAGE_DATA para la carpeta privada de la app.
    data_dir = os.getenv("FLET_APP_STORAGE_DATA", os.getcwd())
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        
    db_path = os.path.join(data_dir, "database.db")
    
    # Conexión estándar
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=DELETE;') # Modo compatible para móviles
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Tabla Configuración
    conn.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            id INTEGER PRIMARY KEY, 
            tasa_dia REAL
        )""")
    # Tabla Marcas
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marca (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT
        )""")
    # Tabla Productos
    conn.execute("""
        CREATE TABLE IF NOT EXISTS producto (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT, 
            marca_id INTEGER, 
            precio REAL, 
            moneda TEXT DEFAULT 'USD',
            FOREIGN KEY(marca_id) REFERENCES marca(id)
        )""")
    
    # Insertar tasa inicial si la tabla está vacía
    res = conn.execute("SELECT count(*) FROM configuracion").fetchone()
    if res[0] == 0:
        conn.execute("INSERT INTO configuracion (id, tasa_dia) VALUES (1, 36.50)")
        
    conn.commit()
    conn.close()

# --- 2. APLICACIÓN PRINCIPAL ---
def main(page: ft.Page):
    init_db() # Inicializar tablas al arrancar
    
    page.title = "SOPSoft ERP"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0f0f0f"
    
    # Ajuste de Header para evitar Notch/Isla en móviles
    page.padding = ft.padding.only(top=45, left=15, right=15, bottom=10)

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
        
        # Cargar Productos
        search_val = f"%{search_bar.value}%"
        productos = conn.execute("""
            SELECT p.id, p.nombre, m.nombre AS marca_nom, p.marca_id, p.precio, p.moneda 
            FROM producto p LEFT JOIN marca m ON p.marca_id = m.id 
            WHERE p.nombre LIKE ? OR m.nombre LIKE ? ORDER BY p.id DESC
        """, (search_val, search_val)).fetchall()

        for p in productos:
            p_base = float(p['precio'])
            es_usd = (p['moneda'] or "USD") == "USD"
            v_usd = p_base if es_usd else p_base / tasa_actual
            v_bs = p_base * tasa_actual if es_usd else p_base
            
            lista_productos.controls.append(ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(p['nombre'], weight="bold"), 
                        ft.Text(f"{p['marca_nom'] or 'Sin Marca'}", size=11, color="grey")
                    ], expand=True),
                    ft.Column([
                        ft.Text(f"${v_usd:.2f}", color="green", weight="bold"), 
                        ft.Text(f"{v_bs:.2f} Bs", size=10, color="amber")
                    ], horizontal_alignment="end"),
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda _, x=p: abrir_editar_prod(x)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", on_click=lambda _, id=p['id']: eliminar_logic("producto", id))
                ]), padding=12, bgcolor="#1a1a1a", border_radius=10
            ))

        # Cargar Marcas
        marcas = conn.execute("SELECT * FROM marca ORDER BY nombre ASC").fetchall()
        dd_marca.options = [ft.dropdown.Option(key=str(m['id']), text=m['nombre']) for m in marcas]
        
        for m in marcas:
            lista_marcas.controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.SELL_ROUNDED, color="amber", size=20),
                    ft.Text(m['nombre'], weight="bold", expand=True),
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda _, x=m: abrir_editar_marca(x)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", on_click=lambda _, id=m['id']: eliminar_logic("marca", id))
                ]), padding=12, bgcolor="#1a1a1a", border_radius=10
            ))
        conn.close()
        page.update()

    # --- MODALES Y ACCIONES ---
    def cerrar_modales(e):
        modal_tasa.open = modal_marca.open = modal_producto.open = False
        page.update()

    # Modal Tasa
    txt_nueva_tasa = ft.TextField(label="Precio del Dólar (Bs)", keyboard_type=ft.KeyboardType.NUMBER)
    modal_tasa = ft.AlertDialog(
        title=ft.Text("Actualizar Tasa"),
        content=txt_nueva_tasa,
        actions=[ft.TextButton("Cancelar", on_click=cerrar_modales), 
                 ft.FilledButton("Guardar", on_click=lambda _: guardar_tasa())]
    )

    # Modal Marca
    edit_marca_id = ft.Text("")
    txt_nombre_marca = ft.TextField(label="Nombre de la Marca")
    modal_marca = ft.AlertDialog(
        title=ft.Text("Gestionar Marca"),
        content=txt_nombre_marca,
        actions=[ft.TextButton("Cerrar", on_click=cerrar_modales), 
                 ft.FilledButton("Guardar", on_click=lambda _: guardar_marca())]
    )

    # Modal Producto
    edit_prod_id = ft.Text("")
    txt_prod_nombre = ft.TextField(label="Nombre del Producto")
    dd_marca = ft.Dropdown(label="Seleccionar Marca")
    txt_precio_base = ft.TextField(label="Precio Base", keyboard_type=ft.KeyboardType.NUMBER)
    rb_moneda = ft.RadioGroup(content=ft.Row([
        ft.Radio(value="USD", label="$"), ft.Radio(value="BS", label="Bs")
    ]), value="USD")

    modal_producto = ft.AlertDialog(
        title=ft.Text("Gestionar Producto"),
        content=ft.Column([txt_prod_nombre, dd_marca, ft.Text("Moneda base:"), rb_moneda, txt_precio_base], tight=True),
        actions=[ft.TextButton("Cerrar", on_click=cerrar_modales), 
                 ft.FilledButton("Guardar", on_click=lambda _: guardar_producto())]
    )

    # --- FUNCIONES DE GUARDADO ---
    def guardar_tasa():
        if txt_nueva_tasa.value:
            conn = get_db_connection()
            conn.execute("UPDATE configuracion SET tasa_dia=? WHERE id=1", (float(txt_nueva_tasa.value),))
            conn.commit(); conn.close(); obtener_tasa(); cerrar_modales(None); refrescar_vistas()

    def guardar_marca():
        if txt_nombre_marca.value:
            conn = get_db_connection()
            if edit_marca_id.value:
                conn.execute("UPDATE marca SET nombre=? WHERE id=?", (txt_nombre_marca.value, edit_marca_id.value))
            else:
                conn.execute("INSERT INTO marca (nombre) VALUES (?)", (txt_nombre_marca.value,))
            conn.commit(); conn.close(); cerrar_modales(None); refrescar_vistas()

    def guardar_producto():
        if txt_prod_nombre.value and dd_marca.value and txt_precio_base.value:
            conn = get_db_connection()
            if edit_prod_id.value:
                conn.execute("UPDATE producto SET nombre=?, marca_id=?, precio=?, moneda=? WHERE id=?", 
                             (txt_prod_nombre.value, dd_marca.value, float(txt_precio_base.value), rb_moneda.value, edit_prod_id.value))
            else:
                conn.execute("INSERT INTO producto (nombre, marca_id, precio, moneda) VALUES (?, ?, ?, ?)", 
                             (txt_prod_nombre.value, dd_marca.value, float(txt_precio_base.value), rb_moneda.value))
            conn.commit(); conn.close(); cerrar_modales(None); refrescar_vistas()

    def abrir_editar_prod(p):
        edit_prod_id.value = str(p['id']); txt_prod_nombre.value = p['nombre']; dd_marca.value = str(p['marca_id'])
        txt_precio_base.value = str(p['precio']); rb_moneda.value = p['moneda'] or "USD"
        modal_producto.open = True; page.update()

    def abrir_editar_marca(m):
        edit_marca_id.value = str(m['id']); txt_nombre_marca.value = m['nombre']
        modal_marca.open = True; page.update()

    def eliminar_logic(tabla, item_id):
        conn = get_db_connection()
        conn.execute(f"DELETE FROM {tabla} WHERE id=?", (item_id,))
        conn.commit(); conn.close(); refrescar_vistas()

    # --- UI ESTRUCTURA TABS ---
    tabs_main = ft.Tabs(
        selected_index=0,
        length=2,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Productos", icon=ft.Icons.SHOPPING_BAG),
                        ft.Tab(label="Marcas", icon=ft.Icons.SELL),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        ft.Column([search_bar, lista_productos], expand=True),
                        lista_marcas,
                    ]
                )
            ]
        )
    )

    header = ft.Row([
        ft.Text("SOPSoft ERP", size=22, weight="bold"),
        ft.Container(
            content=text_tasa_header, padding=10, bgcolor="blue900", border_radius=8, 
            on_click=lambda _: setattr(modal_tasa, "open", True) or page.update()
        )
    ], alignment="spaceBetween")

    page.floating_action_button = ft.FloatingActionButton(
        icon=ft.Icons.ADD, 
        bgcolor="blue",
        on_click=lambda _: abrir_nuevo_segun_tab()
    )

    def abrir_nuevo_segun_tab():
        # Limpiar campos antes de abrir
        if tabs_main.selected_index == 0:
            edit_prod_id.value = ""; txt_prod_nombre.value = ""; txt_precio_base.value = ""; dd_marca.value = None
            modal_producto.open = True
        else:
            edit_marca_id.value = ""; txt_nombre_marca.value = ""
            modal_marca.open = True
        page.update()

    # Agregar modales al overlay
    page.overlay.extend([modal_tasa, modal_producto, modal_marca])
    
    # Carga Inicial
    page.add(header, ft.Divider(height=10, color="transparent"), tabs_main)
    obtener_tasa()
    refrescar_vistas()

if __name__ == "__main__":
    ft.app(target=main)