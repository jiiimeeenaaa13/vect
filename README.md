python src/procesar.py assets/ejemplos/tu_foto.jpg threshold

def quitar_fondo(ruta, umbral_bloque=25, const_c=10):
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
    masc = cv2.morphologyEx(masc, cv2.MORPH_OPEN, kernel)
    masc = cv2.morphologyEx(masc, cv2.MORPH_CLOSE, kernel)

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_rgba = np.dstack((img_rgb, masc))
    return Image.fromarray(img_rgba, mode="RGBA")

    


    with open(ruta, "rb") as f:
        datos_entrada = f.read()
    datos_salida = rembg_remove(datos_entrada)
    return Image.open(io.BytesIO(datos_salida)).convert("RGBA")