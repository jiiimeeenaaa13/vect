# python src/procesarFinal.py assets/ejemplos/img3.jpg threshold
import io
import os
import sys  

import cv2
import numpy as np
import vtracer
from PIL import Image
from rembg import remove as rembg_remove

# evitamos que se pete la memoria si la foto es demasiado grande ej:4k
# se calcula la escala y reduce la imagen manteniendo la proporción, si el lado mayor es menor que lado_maximo no hace nada
def _redimensionar_cv2_si_necesario(img_bgr, lado_maximo=2000):
    alto, ancho = img_bgr.shape[:2]
    lado_mayor = max(alto, ancho)
    if lado_mayor <= lado_maximo:
        return img_bgr
    escala = lado_maximo / lado_mayor
    nuevo_tamano = (int(ancho * escala), int(alto * escala))
    return cv2.resize(img_bgr, nuevo_tamano, interpolation=cv2.INTER_AREA)

# lo mismo que la función anterior pero adaptandose a objetos de imagen de PIL, que es lo que usa rembg
def _redimensionar_pil_si_necesario(imagen, lado_maximo=2000):
    ancho, alto = imagen.size
    lado_mayor = max(ancho, alto)
    if lado_mayor <= lado_maximo:
        return imagen
    escala = lado_maximo / lado_mayor
    nuevo_tamano = (int(ancho * escala), int(alto * escala))
    return imagen.resize(nuevo_tamano, Image.LANCZOS)


def quitar_fondo(ruta, umbral_bloque=25, const_c=10, area_minima=3,
                  umbral_blanco=200, lado_maximo=2000, tamano_cierre=3):

    img_bgr = cv2.imread(ruta)
    if img_bgr is None:
        raise FileNotFoundError(f"No se pudo cargar la imagen: {ruta}")
    img_bgr = _redimensionar_cv2_si_necesario(img_bgr, lado_maximo)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
 
    masc = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY_INV, umbral_bloque, const_c)

    b, g, r = cv2.split(img_bgr)
    es_casi_blanco = (r >= umbral_blanco) & (g >= umbral_blanco) & (b >= umbral_blanco)
    masc[es_casi_blanco] = 0

    kernel_cierre = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (tamano_cierre, tamano_cierre))
    masc = cv2.morphologyEx(masc, cv2.MORPH_CLOSE, kernel_cierre)

    n_etiquetas, etiquetas, stats, _ = cv2.connectedComponentsWithStats(masc, connectivity=8)
    areas = stats[:, cv2.CC_STAT_AREA]
    etiquetas_validas = areas >= area_minima
    etiquetas_validas[0] = False 
    masc = np.where(etiquetas_validas[etiquetas], 255, 0).astype(np.uint8)
    #----------------------------------------------------------------
    
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_rgba = np.dstack((img_rgb, masc))
    return Image.fromarray(img_rgba, mode="RGBA")


def quitar_fondo_ia(ruta, umbral_blanco=240, lado_maximo=2000):
    
    imagen_entrada = Image.open(ruta).convert("RGB")
    imagen_entrada = _redimensionar_pil_si_necesario(imagen_entrada, lado_maximo)

    buffer_entrada = io.BytesIO()
    imagen_entrada.save(buffer_entrada, format="PNG")
    datos_salida = rembg_remove(buffer_entrada.getvalue())
    imagen = Image.open(io.BytesIO(datos_salida)).convert("RGBA")

    arr = np.array(imagen)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    es_blanco = (r >= umbral_blanco) & (g >= umbral_blanco) & (b >= umbral_blanco)
    arr[:, :, 3] = np.where(es_blanco, 0, a)

    return Image.fromarray(arr, mode="RGBA")


def guardar_png_transp(imagen, ruta_salida):
    
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    imagen.save(ruta_salida, "PNG")


def vectorizar_svg(ruta_png_transp, ruta_svg_salida):
   
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