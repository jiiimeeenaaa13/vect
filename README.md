# Vectorizador de Dibujos 

Aplicación de escritorio desarrollada en Python para la conversión automatizada de dibujos, bocetos e ilustraciones en formato rastear (JPG/PNG) a imágenes vectoriales SVG y archivos PNG con fondo transparente.

## Características principales

* **Eliminación de fondo por Umbral Adaptativo (Threshold):** Diseñado para bocetos digitalizados y dibujos hechos a mano sobre papel.
* **Eliminación de fondo por Inteligencia Artificial (`rembg`):** Diseñado para imágenes complejas o ilustraciones con color.Se usa si se quiere mantener el dibujo tal cual pero cambiando de fondo (con colores incluidos)
* **Vectorización automática:** Conversión directa a SVG estructurado utilizando `vtracer`.
* **Aumento de resolución (x2):** Interpolación *LANCZOS* para duplicar la densidad de píxeles y regenerar la capa vectorial.
* **Previsualización interactiva:** Comparativa en tiempo real (Original vs Resultado) con vista previa ampliada.
* **Soporte Drag & Drop:** Arrastra y suelta imágenes directamente dentro de la aplicación.

---

## Requisitos e Instalación

### Requisitos previos
* Python 3.10 o superior.

$ source venv/bin/activate
$ pip install -r requirements.txt

Para procesar sin interfaz : 
$ python src/procesarFinal.py assets/ejemplos/dibujo.jpg threshold

Probar la app desde la interfaz : 
$ python src/interfaz.py