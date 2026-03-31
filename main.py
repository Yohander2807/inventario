import flet as ft
import sqlite3
import os

def get_db_connection():
    data_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "database.db")
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn

def main(page: ft.Page):
    page.title = "SOPSoft ERP"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0f0f0f"
    page.padding = ft.padding.only(top=45, left=15, right=15, bottom=10)

    tasa_actual = 36.50

    # --- CONTENEDORES DE LISTAS ---
    lista_productos = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    lista_marcas = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    text_tasa_header = ft.Text("Cargando...", size=14, weight="bold")
    search_bar = ft.TextField(hint_text="Buscar...", prefix_icon=ft.Icons.SEARCH, on_change=lambda _: refrescar_vistas())

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

    def refrescar_vistas():
        lista_productos.controls.clear()
        lista_marcas.controls.clear()
        conn = get_db_connection()
        
        # Productos
        search_val = f"%{search_bar.value}%"
        productos = conn.execute("""
            SELECT p.id, p.nombre, m.nombre AS marca, p.marca_id, p.precio, p.moneda 
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
                    ft.Column([ft.Text(p['nombre'], weight="bold"), ft.Text(f"{p['marca'] or 'Generico'}", size=11, color="grey")], expand=True),
                    ft.Column([ft.Text(f"${v_usd:.2f}", color="green"), ft.Text(f"{v_bs:.2f} Bs", size=10)], horizontal_alignment="end"),
                    ft.IconButton(ft.Icons.EDIT, on_click=lambda _, x=p: abrir_editar_prod(x)),
                ]), padding=10, bgcolor="#1a1a1a", border_radius=10
            ))

        # Marcas
        marcas = conn.execute("SELECT * FROM marca ORDER BY nombre ASC").fetchall()
        dd_marca.options = [ft.dropdown.Option(key=str(m['id']), text=m['nombre']) for m in marcas]
        for m in marcas:
            lista_marcas.controls.append(ft.Container(
                content=ft.Row([
                    ft.Text(m['nombre'], weight="bold", expand=True),
                    ft.IconButton(ft.Icons.EDIT, on_click=lambda _, x=m: abrir_editar_marca(x)),
                    ft.IconButton(ft.Icons.DELETE, icon_color="red", on_click=lambda _, id=m['id']: eliminar_logic("marca", id))
                ]), padding=10, bgcolor="#1a1a1a", border_radius=10
            ))
        conn.close()
        page.update()

    # --- MODALES ---
    def cerrar_modal(e):
        modal_tasa.open = modal_marca.open = modal_producto.open = False
        page.update()

    # Modal Tasa
    txt_nueva_tasa = ft.TextField(label="Nueva Tasa", keyboard_type=ft.KeyboardType.NUMBER)
    modal_tasa = ft.AlertDialog(
        title=ft.Text("Tasa"), 
        content=txt_nueva_tasa, 
        actions=[ft.FilledButton("Guardar", on_click=lambda _: guardar_tasa())]
    )

    # Modal Marca (EL QUE FALTABA)
    edit_marca_id = ft.Text("")
    txt_nombre_marca = ft.TextField(label="Nombre de Marca")
    modal_marca = ft.AlertDialog(
        title=ft.Text("Gestionar Marca"),
        content=txt_nombre_marca,
        actions=[ft.TextButton("Cerrar", on_click=cerrar_modal), ft.FilledButton("Guardar", on_click=lambda _: guardar_marca())]
    )

    # Modal Producto
    edit_prod_id = ft.Text(""); txt_prod_nombre = ft.TextField(label="Nombre"); dd_marca = ft.Dropdown(label="Marca")
    txt_precio_base = ft.TextField(label="Precio", keyboard_type=ft.KeyboardType.NUMBER)
    rb_moneda = ft.RadioGroup(content=ft.Row([ft.Radio(value="USD", label="$"), ft.Radio(value="BS", label="Bs")]), value="USD")
    modal_producto = ft.AlertDialog(
        title=ft.Text("Producto"),
        content=ft.Column([txt_prod_nombre, dd_marca, rb_moneda, txt_precio_base], tight=True),
        actions=[ft.TextButton("Cerrar", on_click=cerrar_modal), ft.FilledButton("Guardar", on_click=lambda _: guardar_prod())]
    )

    # --- LÓGICA DE GUARDADO ---
    def guardar_tasa():
        conn = get_db_connection()
        conn.execute("UPDATE configuracion SET tasa_dia=?", (float(txt_nueva_tasa.value),))
        conn.commit(); conn.close(); obtener_tasa(); cerrar_modal(None); refrescar_vistas()

    def guardar_marca():
        if txt_nombre_marca.value:
            conn = get_db_connection()
            if edit_marca_id.value:
                conn.execute("UPDATE marca SET nombre=? WHERE id=?", (txt_nombre_marca.value, edit_marca_id.value))
            else:
                conn.execute("INSERT INTO marca (nombre) VALUES (?)", (txt_nombre_marca.value,))
            conn.commit(); conn.close(); cerrar_modal(None); refrescar_vistas()

    def guardar_prod():
        if txt_prod_nombre.value and dd_marca.value:
            conn = get_db_connection()
            if edit_prod_id.value:
                conn.execute("UPDATE producto SET nombre=?, marca_id=?, precio=?, moneda=? WHERE id=?", (txt_prod_nombre.value, dd_marca.value, float(txt_precio_base.value), rb_moneda.value, edit_prod_id.value))
            else:
                conn.execute("INSERT INTO producto (nombre, marca_id, precio, moneda) VALUES (?, ?, ?, ?)", (txt_prod_nombre.value, dd_marca.value, float(txt_precio_base.value), rb_moneda.value))
            conn.commit(); conn.close(); cerrar_modal(None); refrescar_vistas()

    # --- APERTURA ---
    def abrir_editar_prod(p):
        edit_prod_id.value = str(p['id']); txt_prod_nombre.value = p['nombre']; dd_marca.value = str(p['marca_id'])
        txt_precio_base.value = str(p['precio']); rb_moneda.value = p['moneda'] or "USD"
        modal_producto.open = True; page.update()

    def abrir_editar_marca(m):
        edit_marca_id.value = str(m['id']); txt_nombre_marca.value = m['nombre']
        modal_marca.open = True; page.update()

    def eliminar_logic(tab, id):
        conn = get_db_connection(); conn.execute(f"DELETE FROM {tab} WHERE id=?", (id,)); conn.commit(); conn.close(); refrescar_vistas()

    # --- UI ---
    tabs_main = ft.Tabs(
        selected_index=0, expand=True,
        length=2,
        content=ft.Column(expand=True, controls=[
            ft.TabBar(tabs=[ft.Tab(label="Productos", icon=ft.Icons.SHOPPING_BAG), ft.Tab(label="Marcas", icon=ft.Icons.SELL)]),
            ft.TabBarView(expand=True, controls=[ft.Column([search_bar, lista_productos], expand=True), lista_marcas])
        ])
    )

    header = ft.Row([
        ft.Text("SOPSoft ERP", size=22, weight="bold"),
        ft.Container(text_tasa_header, padding=8, bgcolor="blue900", border_radius=8, on_click=lambda _: setattr(modal_tasa, "open", True) or page.update())
    ], alignment="spaceBetween")

    page.floating_action_button = ft.FloatingActionButton(
        icon=ft.Icons.ADD, 
        on_click=lambda _: (setattr(edit_prod_id, "value", ""), setattr(txt_prod_nombre, "value", ""), 
                           setattr(edit_marca_id, "value", ""), setattr(txt_nombre_marca, "value", ""),
                           setattr(modal_producto if tabs_main.selected_index==0 else modal_marca, "open", True), page.update())
    )

    page.overlay.extend([modal_tasa, modal_producto, modal_marca])
    page.add(header, ft.Divider(height=10, color="transparent"), tabs_main)
    obtener_tasa(); refrescar_vistas()

ft.app(target=main)