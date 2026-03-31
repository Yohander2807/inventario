import flet as ft
import sqlite3
import os

# --- CONFIGURACIÓN DE BASE DE DATOS ---
def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'database.db')
    if not os.path.exists(os.path.dirname(db_path)):
        os.makedirs(os.path.dirname(db_path))
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    conn.execute('PRAGMA foreign_keys = ON;')
    conn.row_factory = sqlite3.Row
    return conn

def main(page: ft.Page):
    page.title = "SOPSoft ERP - Sistema de inventario"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0f0f0f"
    page.padding = 20

    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    
    if os.path.exists(icon_path):
        # Esta es la propiedad que establece el icono de la ventana
        page.window.icon = icon_path 
    else:
        print(f"Aviso: No se encontró el icono en {icon_path}. Usando icono por defecto.")
    
    tasa_actual = 36.50

    # --- ELEMENTOS DE UI (Contenedores de listas) ---
    lista_productos = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    lista_marcas = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    text_tasa_header = ft.Text("Cargando...", size=14, weight="bold")

    # --- FUNCIONES DE LÓGICA ---
    def obtener_tasa():
        nonlocal tasa_actual
        try:
            conn = get_db_connection()
            tasa_row = conn.execute("SELECT tasa_dia FROM configuracion LIMIT 1").fetchone()
            tasa_actual = float(tasa_row['tasa_dia']) if tasa_row else 36.50
            conn.close()
        except: tasa_actual = 36.50
        text_tasa_header.value = f"Tasa: {tasa_actual} Bs"
        page.update()

    def obtener_marcas():
        conn = get_db_connection()
        marcas = conn.execute("SELECT * FROM marca ORDER BY nombre ASC").fetchall()
        conn.close()
        return marcas

    def obtener_productos(search=""):
        conn = get_db_connection()
        query = """
            SELECT p.id, p.nombre, m.nombre AS marca, p.marca_id, p.precio 
            FROM producto p LEFT JOIN marca m ON p.marca_id = m.id 
            WHERE p.nombre LIKE ? OR m.nombre LIKE ?
            ORDER BY p.id DESC
        """
        search_val = f"%{search}%"
        productos = conn.execute(query, (search_val, search_val)).fetchall()
        conn.close()
        return productos

    # --- REFRESCAR VISTAS (Separadas por contenedor) ---
    def refrescar_vistas(e=None):
        # Actualizar Productos
        lista_productos.controls.clear()
        marcas = obtener_marcas()
        dd_marca.options = [ft.dropdown.Option(key=str(m['id']), text=m['nombre']) for m in marcas]
        
        for p in obtener_productos(search_bar.value):
            p_bs = float(p['precio']) * tasa_actual
            lista_productos.controls.append(ft.Container(
                content=ft.Row([
                    ft.Column([ft.Text(p['nombre'], weight="bold"), ft.Text(p['marca'] or "Generico", size=11, color="grey")], expand=True),
                    ft.Column([ft.Text(f"${p['precio']}", color="green", weight="bold"), ft.Text(f"{p_bs:.2f} Bs", size=10)], horizontal_alignment="end"),
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda _, x=p: abrir_editar_prod(x)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", on_click=lambda _, id=p['id']: eliminar_logic("producto", id))
                ]), padding=12, bgcolor="#1a1a1a", border_radius=10
            ))

        # Actualizar Marcas
        lista_marcas.controls.clear()
        for m in marcas:
            lista_marcas.controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.SELL_ROUNDED, color="amber"),
                    ft.Text(m['nombre'], weight="bold", expand=True),
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda _, x=m: abrir_editar_marca(x)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", on_click=lambda _, id=m['id']: eliminar_logic("marca", id))
                ]), padding=12, bgcolor="#1a1a1a", border_radius=10
            ))
        page.update()

    # --- MODALES ---
    def cerrar_modal(e):
        modal_tasa.open = False; modal_marca.open = False; modal_producto.open = False
        page.update()

    # Modal Tasa
    txt_nueva_tasa = ft.TextField(label="Nueva Tasa (Bs)", keyboard_type=ft.KeyboardType.NUMBER)
    modal_tasa = ft.AlertDialog(title=ft.Text("Actualizar Tasa"), content=txt_nueva_tasa,
        actions=[ft.TextButton("Cancelar", on_click=cerrar_modal), ft.ElevatedButton("Actualizar", on_click=lambda _: guardar_tasa())])

    def guardar_tasa():
        if txt_nueva_tasa.value:
            conn = get_db_connection()
            conn.execute("UPDATE configuracion SET tasa_dia = ?", (float(txt_nueva_tasa.value),))
            conn.commit(); conn.close(); obtener_tasa(); cerrar_modal(None); refrescar_vistas()

    # Modal Marcas
    edit_marca_id = ft.Text(""); txt_nombre_marca = ft.TextField(label="Nombre de la Marca")
    modal_marca = ft.AlertDialog(title=ft.Text("Gestionar Marca"), content=txt_nombre_marca,
        actions=[ft.TextButton("Cancelar", on_click=cerrar_modal), ft.ElevatedButton("Guardar", on_click=lambda _: guardar_marca_logic())])

    def guardar_marca_logic():
        if txt_nombre_marca.value:
            conn = get_db_connection()
            if edit_marca_id.value: conn.execute("UPDATE marca SET nombre=? WHERE id=?", (txt_nombre_marca.value, edit_marca_id.value))
            else: conn.execute("INSERT INTO marca (nombre) VALUES (?)", (txt_nombre_marca.value,))
            conn.commit(); conn.close(); cerrar_modal(None); refrescar_vistas()

    # Modal Productos
    edit_prod_id = ft.Text(""); txt_prod_nombre = ft.TextField(label="Nombre")
    dd_marca = ft.Dropdown(label="Marca")
    txt_prod_precio_usd = ft.TextField(label="Precio ($)", expand=True, on_change=lambda e: calcular_precios(e, "usd"))
    txt_prod_precio_bs = ft.TextField(label="Precio (Bs)", expand=True, on_change=lambda e: calcular_precios(e, "bs"))

    def calcular_precios(e, modo):
        try:
            if modo == "bs" and txt_prod_precio_bs.value:
                txt_prod_precio_usd.value = f"{float(txt_prod_precio_bs.value) / tasa_actual:.2f}"
            elif modo == "usd" and txt_prod_precio_usd.value:
                txt_prod_precio_bs.value = f"{float(txt_prod_precio_usd.value) * tasa_actual:.2f}"
        except: pass
        page.update()

    modal_producto = ft.AlertDialog(title=ft.Text("Gestionar Producto"),
        content=ft.Column([txt_prod_nombre, dd_marca, ft.Row([txt_prod_precio_usd, txt_prod_precio_bs])], tight=True),
        actions=[ft.TextButton("Cancelar", on_click=cerrar_modal), ft.ElevatedButton("Guardar", on_click=lambda _: guardar_producto_logic())])

    def guardar_producto_logic():
        if txt_prod_nombre.value and dd_marca.value and txt_prod_precio_usd.value:
            conn = get_db_connection()
            if edit_prod_id.value: conn.execute("UPDATE producto SET nombre=?, marca_id=?, precio=? WHERE id=?", (txt_prod_nombre.value, dd_marca.value, txt_prod_precio_usd.value, edit_prod_id.value))
            else: conn.execute("INSERT INTO producto (nombre, marca_id, precio) VALUES (?, ?, ?)", (txt_prod_nombre.value, dd_marca.value, txt_prod_precio_usd.value))
            conn.commit(); conn.close(); cerrar_modal(None); refrescar_vistas()

    # --- FUNCIONES DE APERTURA ---
    def abrir_editar_prod(p):
        edit_prod_id.value = str(p['id']); txt_prod_nombre.value = p['nombre']; dd_marca.value = str(p['marca_id'])
        txt_prod_precio_usd.value = str(p['precio']); calcular_precios(None, "usd")
        modal_producto.open = True; page.update()

    def abrir_editar_marca(m):
        edit_marca_id.value = str(m['id']); txt_nombre_marca.value = m['nombre']
        modal_marca.open = True; page.update()

    def eliminar_logic(tabla, id):
        conn = get_db_connection()
        try:
            conn.execute(f"DELETE FROM {tabla} WHERE id=?", (id,))
            conn.commit()
        except:
            page.snack_bar = ft.SnackBar(ft.Text("Vínculo activo detectado")); page.snack_bar.open = True
        conn.close(); refrescar_vistas()

    # --- UI PRINCIPAL ---
    header = ft.Row([
        ft.Text("Sistema de Inventario", size=24, weight="bold"),
        ft.Container(content=text_tasa_header, padding=10, bgcolor=ft.Colors.BLUE_900, border_radius=8, 
                     on_click=lambda _: setattr(modal_tasa, "open", True) or page.update())
    ], alignment="spaceBetween")

    search_bar = ft.TextField(hint_text="Buscar productos...", prefix_icon=ft.Icons.SEARCH, on_change=refrescar_vistas)

    # --- IMPLEMENTACIÓN DE TABS SEGÚN TU EJEMPLO ---
    tabs_control = ft.Tabs(
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
                        # VISTA 1: PRODUCTOS
                        ft.Column([search_bar, lista_productos], expand=True),
                        # VISTA 2: MARCAS
                        ft.Column([lista_marcas], expand=True),
                    ]
                )
            ]
        )
    )

    def abrir_modal_nuevo():
        if tabs_control.selected_index == 0:
            edit_prod_id.value = ""; txt_prod_nombre.value = ""; dd_marca.value = None
            txt_prod_precio_usd.value = ""; txt_prod_precio_bs.value = ""; modal_producto.open = True
        else:
            edit_marca_id.value = ""; txt_nombre_marca.value = ""; modal_marca.open = True
        page.update()

    page.floating_action_button = ft.FloatingActionButton(
        icon=ft.Icons.ADD, bgcolor="blue", on_click=lambda _: abrir_modal_nuevo()
    )

    page.overlay.extend([modal_tasa, modal_marca, modal_producto])
    page.add(header, ft.Divider(height=10, color="transparent"), tabs_control)
    
    obtener_tasa()
    refrescar_vistas()

if __name__ == "__main__":
    ft.app(target=main)