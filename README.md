# Vectorizador de Dibujos

Aplicación de escritorio desarrollada en **Python** y **PySide6** para la conversión automatizada de dibujos, bocetos e ilustraciones en formato ráster (`JPG` / `JPEG` / `PNG`) a imágenes vectoriales **SVG** y archivos **PNG con fondo transparente**.

---

##  Características Principales

* **Eliminación de fondo por Umbral Adaptativo (Threshold):**
  * Diseñado para bocetos digitalizados y dibujos a mano alzada sobre papel.
  * Incluye controles de **nivel de limpieza mórfica** (*"Detalle más fino"* o *"Buen detalle global, más líneas"*) para eliminar imperfecciones o ruido del escaneo.

* **Eliminación de fondo por Inteligencia Artificial (`rembg` / ONNX):**
  * Diseñado para ilustraciones complejas o dibujos a color.
  * Aisla el dibujo manteniendo la paleta de colores y removiendo automáticamente el fondo blanco o uniforme.

* **Procesamiento Asíncrono no Bloqueante (`QThread`):**
  * El procesamiento de imágenes y la carga del modelo de IA se ejecutan en un hilo secundario en segundo plano.
  * La interfaz de usuario mantendrá la fluidez y respuesta constante sin quedarse congelada.

* **Vectorización Automática:**
  * Conversión directa del resultado transparente a formato **SVG estructurado** utilizando `vtracer`.

* **Aumento de Resolución (x2):**
  * Escalado mediante interpolación **LANCZOS** para duplicar la densidad de píxeles y regenerar la capa vectorial SVG con mayor definición.

* **Previsualización Interactiva & Zoom:**
  * Vista comparativa en tiempo real (*Original vs. Resultado* sobre fondo de damero transparente).
  * Modal de vista previa ampliada con soporte de desplazamiento (scroll) al hacer clic en el resultado.

* **Soporte Drag & Drop:**
  * Arrastra y suelta imágenes directamente dentro del área designada de la interfaz.

* **Soporte Completo para Ejecutables (`.exe`):**
  * Configurado con `multiprocessing.freeze_support()` para evitar bucles infinitos de procesos durante la ejecución empaquetada en Windows.

---

##  Requisitos e Instalación

### Requisitos previos
* **Python 3.10** o superior.

### Instalación de dependencias

1. Crea y activa un entorno virtual:
   ```bash
   python -m venv venv
   # En Linux/macOS:
   source venv/bin/activate
   # En Windows:
   venv\Scripts\activate

2. Dependencias principales:
    ```bash
    pip install -r requirements.txt
3. Ejecutar interfaz gráfica: 
    ```bash
    python interfaz.py

4. Ejecutar imagen en contro sin aplicación, por WSL:
    ```bash
    python procesarFinal.py assets/ejemplos/dibujo.jpg [metodo]

### Obtenr el punto .exe

1. Dentro del directorio de trabajo y del venv: (Conveniente hacerlo en PowerShell)
    ```bash
    pyinstaller VectorizadorApp.spec --noconfirm
