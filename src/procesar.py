"""
PIPELINE, convertir dubujo (foto/escaneo) en PNG transparente  SVG vectorial

python src/procesar.py <rutaImagen> [threshold/ia]
ej: python src/procesar.py assets/ejemplos/dibujo.jpg threshold 

"""
import io
import os
import sys

import cv2
import numpy as np
import vtracer
from PIL import Image
from rembg import remove as rembg_remove

def quitar_fondo(ruta, umbral_bloque=25, const_c=10,area_minima=3):
    """+
    binarización adaptiva con OpenCV para quitar el fondo
    Si es fondo blanco uniforme y buena iluminación 
    """
    img_bgr = cv2.imread(ruta)
    if img_bgr is None: 
        raise FileNotFoundError(f"No se pudo cargar la imagen: {ruta}")

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    """ trazo "oscuro" pasa a blanco 255, el fondo a negro 0 -> canal alpha"""
    masc = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV, umbral_bloque, const_c)

    """ quitar puntos de ruido sueltos (OPEN) y rellenar huecos dentro del trazo (CLOSE) """
    kernel = np.ones((3,3), np.uint8)
    masc = cv2.morphologyEx(masc, cv2.MORPH_CLOSE, kernel)

    #evitamos eliminar puntos pequeños aparentemente no importantes
    n_etiquetas, etiquetas, stats, _ = cv2.connectedComponentsWithStats(masc, connectivity=8)
    masc_limpia = np.zeros_like(masc)
    for i in range(1, n_etiquetas):  # el índice 0 es el fondo, se salta
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= area_minima:
            masc_limpia[etiquetas == i] = 255
    masc = masc_limpia

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_rgba = np.dstack((img_rgb, masc))
    return Image.fromarray(img_rgba, mode="RGBA")

def quitar_fondo_ia(ruta, umbral_blanco=240):
    """ quitamos el fondo usando el modelo U2-Net (rembg), en LOCAL, meojr para sombras o texturas"""
    with open(ruta, "rb") as f:
        datos_entrada = f.read()
    datos_salida = rembg_remove(datos_entrada)
    imagen = Image.open(io.BytesIO(datos_salida)).convert("RGBA")

    arr = np.array(imagen)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    es_blanco = (r >= umbral_blanco) & (g >= umbral_blanco) & (b >= umbral_blanco)
    arr[:, :, 3] = np.where(es_blanco, 0, a)

    return Image.fromarray(arr, mode="RGBA")

def guardar_png_transp(imagen, ruta_salida):
    """ guarda img PIL RGBA como PNG con canal alpha"""
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    imagen.save(ruta_salida, "PNG")

def vectorizar_svg(ruta_png_transp, ruta_svg_salida):
    """ convertir PNG transparente en SVG vectorial usando vctracer"""
    os.makedirs(os.path.dirname(ruta_svg_salida), exist_ok=True)
    vtracer.convert_image_to_svg_py(
        ruta_png_transp, ruta_svg_salida,
        colormode="color",
        hierarchical="stacked",
        mode="spline",
        filter_speckle=4,
        color_precision=6,
        layer_difference=16,
        corner_threshold=60,
        length_threshold=4.0,
        max_iterations=10,
        splice_threshold=45,
        path_precision=3,
    )

def procesar_img(ruta_entrada, carp_salida="output", metodo="threshold"):
    """  quitar fondo con el metodo indicado y genera tanto PNG transparente como SVG vectorial, devuelve (ruta_png, ruta_svg """
    nombre_base = os.path.splitext(os.path.basename(ruta_entrada))[0]
    sufijo = "" if metodo == "threshold" else f"_{metodo}"
    nombre_salida = f"{nombre_base}{sufijo}"
    ruta_png = os.path.join(carp_salida, f"{nombre_salida}.png")
    ruta_svg = os.path.join(carp_salida, f"{nombre_salida}.svg")

    if metodo == "threshold":
        img = quitar_fondo(ruta_entrada)
    elif metodo == "ia":
        img = quitar_fondo_ia(ruta_entrada)
    else:
        raise ValueError(f"Método desconocido: {metodo}. Use 'threshold' o 'ia'.")
    
    guardar_png_transp(img, ruta_png)
    vectorizar_svg(ruta_png, ruta_svg)

    return ruta_png, ruta_svg

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python src/procesar.py <rutaImagen> [threshold/ia]")
        sys.exit(1)

    ruta_entrada = sys.argv[1]
    metodo = sys.argv[2] if len(sys.argv) > 2 else "threshold"

    ruta_png, ruta_svg = procesar_img(ruta_entrada, "output", metodo)
    print(f"PNG  guardado en: {ruta_png}")
    print(f"SVG vectorial guardado : {ruta_svg}")

