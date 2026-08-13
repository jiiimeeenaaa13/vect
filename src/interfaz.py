import sys
import os
import multiprocessing

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import re
import shutil
import tempfile
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox,
    QFrame, QSizePolicy, QInputDialog, QDialog, QScrollArea
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QThread, Signal
from PIL import Image
from PIL.ImageQt import ImageQt

from procesarFinal import procesar_img, vectorizar_svg

EXTENSIONES_VALIDAS = (".jpg", ".jpeg", ".png")

HOJA_ESTILOS = """
QWidget { background-color: #f5f5f7; font-family: 'Segoe UI', sans-serif; font-size: 13px; color: #222; }
QFrame#barraLateral { background-color: #ffffff; border-right: 1px solid #e0e0e0; }
QLabel#tituloApp { font-size: 17px; font-weight: 600; padding-bottom: 6px; }
QLabel#subtitulo { color: #777; padding-bottom: 14px; }
QLabel#zonaArrastre {
    border: 2px dashed #b5b5c0; border-radius: 10px; padding: 30px 10px;
    color: #666; background-color: #fafafa;
}
QPushButton {
    background-color: #4a90e2; color: white; border: none;
    border-radius: 6px; padding: 9px 14px; font-weight: 500;
}
QPushButton:hover { background-color: #3a7bc8; }
QPushButton:disabled { background-color: #c7c7cc; color: #f0f0f0; }
QPushButton#botonSecundario { background-color: #eceff3; color: #333; }
QPushButton#botonSecundario:hover { background-color: #dde2e8; }
QLabel#previewBox { border: 1px solid #d0d0d5; border-radius: 8px; background-color: white; }
QLabel#etiquetaEstado { color: #555; padding-top: 4px; }
QLabel#etiquetaSeccion { font-weight: 600; padding-top: 10px; }
"""

class HiloProcesamiento(QThread):
    finalizado = Signal(str, str)
    error = Signal(str)

    def __init__(self, ruta_entrada, carpeta_salida, metodo, nivel_cierre):
        super().__init__()
        self.ruta_entrada = ruta_entrada
        self.carpeta_salida = carpeta_salida
        self.metodo = metodo
        self.nivel_cierre = nivel_cierre

    def run(self):
        try:
            ruta_png, ruta_svg = procesar_img(
                self.ruta_entrada, self.carpeta_salida, self.metodo, tamano_cierre=self.nivel_cierre
            )
            self.finalizado.emit(ruta_png, ruta_svg)
        except Exception as e:
            self.error.emit(str(e))


def _carpeta_inicial_selector():
    return str(Path.home())


def _sanear_nombre_archivo(nombre):
    return re.sub(r'[\\/:*?"<>|]', "", nombre).strip()


def _fondo_cuadros(ancho, alto, tamano_cuadro=16):
    base_size = tamano_cuadro * 2
    tile = Image.new("RGB", (base_size, base_size), "white")
    pixeles = tile.load()
    for y in range(base_size):
        for x in range(base_size):
            if (x // tamano_cuadro + y // tamano_cuadro) % 2 == 0:
                pixeles[x, y] = (204, 204, 204)

    fondo = Image.new("RGB", (ancho, alto))
    for y in range(0, alto, base_size):
        for x in range(0, ancho, base_size):
            fondo.paste(tile, (x, y))
    return fondo


def _componer_sobre_cuadros(ruta_png_transparente, max_dim=1000):
    imagen = Image.open(ruta_png_transparente).convert("RGBA")
    if max(imagen.width, imagen.height) > max_dim:
        imagen.thumbnail((max_dim, max_dim), Image.LANCZOS)
    fondo = _fondo_cuadros(imagen.width, imagen.height).convert("RGBA")
    compuesta = Image.alpha_composite(fondo, imagen)
    return compuesta.convert("RGB")


class ZonaArrastre(QLabel):
    def __init__(self, al_hacer_clic):
        super().__init__("Arrastra tu foto aquí\no haz clic para buscarla")
        self.setObjectName("zonaArrastre")
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self._al_hacer_clic = al_hacer_clic

    def mousePressEvent(self, evento):
        self._al_hacer_clic()


class PreviewLabel(QLabel):
    def __init__(self, texto="", al_hacer_clic=None):
        super().__init__(texto)
        self.setObjectName("Caja de previsualización")
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(100, 100)
        self._pixmap = None
        self._texto_defecto = texto
        self._al_hacer_clic = al_hacer_clic
        if al_hacer_clic:
            self.setCursor(Qt.PointingHandCursor)

    def set_image(self, pixmap):
        if pixmap and not pixmap.isNull():
            self._pixmap = pixmap
            self.setText("")
            self.update_pixmap()
        else:
            self._pixmap = None
            super().setPixmap(QPixmap())
            self.setText(self._texto_defecto)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if self._pixmap and not self._pixmap.isNull():
            self.update_pixmap()

    def update_pixmap(self):
        if self._pixmap and not self._pixmap.isNull():
            w, h = self.width(), self.height()
            if w > 10 and h > 10:
                pixmap_escalado = self._pixmap.scaled(
                    w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                super().setPixmap(pixmap_escalado)

    def mousePressEvent(self, evento):
        if self._al_hacer_clic and self._pixmap:
            self._al_hacer_clic()
        super().mousePressEvent(evento)


class VentanaAmpliada(QDialog):
    def __init__(self, ruta_png, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ampliar Resultado")
        self.resize(850, 850)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        area_scroll = QScrollArea()
        area_scroll.setWidgetResizable(True)
        area_scroll.setAlignment(Qt.AlignCenter)
        layout.addWidget(area_scroll)

        compuesta = _componer_sobre_cuadros(ruta_png, max_dim=2000)
        qimagen = ImageQt(compuesta)
        pixmap = QPixmap.fromImage(qimagen)

        etiqueta_imagen = QLabel()
        etiqueta_imagen.setPixmap(pixmap)
        etiqueta_imagen.setAlignment(Qt.AlignCenter)
        area_scroll.setWidget(etiqueta_imagen)


class VentanaPrincipal(QMainWindow):
    NIVELES_CIERRE = [3, 4]
    DESCRIPCIONES_CIERRE = ["Detalle más fino", "Buen detalle global, más líneas"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dibujo → Transparente")
        self.resize(1050, 650)
        self.setAcceptDrops(True)
        self.setStyleSheet(HOJA_ESTILOS)

        self.ruta_imagen_entrada = None
        self.ruta_png_resultado = None
        self.ruta_svg_resultado = None
        self.carpeta_inicial = _carpeta_inicial_selector()
        self.hilo_procesamiento = None

        contenedor = QWidget()
        self.setCentralWidget(contenedor)
        layout_raiz = QHBoxLayout(contenedor)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        barra = QFrame()
        barra.setObjectName("barraLateral")
        barra.setFixedWidth(260)
        layout_barra = QVBoxLayout(barra)
        layout_barra.setContentsMargins(18, 20, 18, 20)
        layout_barra.setSpacing(8)

        titulo = QLabel("Vectorizador")
        titulo.setObjectName("tituloApp")
        layout_barra.addWidget(titulo)

        subtitulo = QLabel("Convierte tu dibujo escaneado en PNG y SVG transparente.")
        subtitulo.setObjectName("subtitulo")
        subtitulo.setWordWrap(True)
        layout_barra.addWidget(subtitulo)

        self.zona_arrastre = ZonaArrastre(self.seleccionar_imagen)
        layout_barra.addWidget(self.zona_arrastre)

        etiqueta_opciones = QLabel("Opciones")
        etiqueta_opciones.setObjectName("etiquetaSeccion")
        layout_barra.addWidget(etiqueta_opciones)

        self.combo_metodo = QComboBox()
        self.combo_metodo.addItems(["Adaptativo", "ia"])
        self.combo_metodo.currentTextChanged.connect(self._actualizar_disponibilidad_opciones)
        layout_barra.addWidget(self.combo_metodo)

        etiqueta_nivel = QLabel("Limpieza")
        etiqueta_nivel.setObjectName("etiquetaSeccion")
        layout_barra.addWidget(etiqueta_nivel)

        self.combo_cierre = QComboBox()
        self.combo_cierre.addItems(self.DESCRIPCIONES_CIERRE)
        self.combo_cierre.setCurrentIndex(0)
        layout_barra.addWidget(self.combo_cierre)

        self.boton_procesar = QPushButton("Procesar")
        self.boton_procesar.clicked.connect(self.procesar)
        self.boton_procesar.setEnabled(False)
        layout_barra.addWidget(self.boton_procesar)

        etiqueta_descarga = QLabel("Acciones")
        etiqueta_descarga.setObjectName("etiquetaSeccion")
        layout_barra.addWidget(etiqueta_descarga)

        self.boton_guardar = QPushButton("Guardar PNG + SVG...")
        self.boton_guardar.setObjectName("botonSecundario")
        self.boton_guardar.clicked.connect(self.guardar_resultados)
        self.boton_guardar.setEnabled(False)
        layout_barra.addWidget(self.boton_guardar)

        self.boton_aumentar = QPushButton("Aumentar resolución (x2)")
        self.boton_aumentar.setObjectName("botonSecundario")
        self.boton_aumentar.clicked.connect(self.aumentar_resolucion)
        self.boton_aumentar.setEnabled(False)
        layout_barra.addWidget(self.boton_aumentar)

        layout_barra.addStretch()

        self.etiqueta_estado = QLabel("Selecciona una imagen para empezar.")
        self.etiqueta_estado.setObjectName("etiquetaEstado")
        self.etiqueta_estado.setWordWrap(True)
        layout_barra.addWidget(self.etiqueta_estado)

        layout_raiz.addWidget(barra)

        panel_preview = QWidget()
        layout_preview = QVBoxLayout(panel_preview)
        layout_preview.setContentsMargins(20, 20, 20, 20)
        layout_preview.setSpacing(10)

        fila_previews = QHBoxLayout()
        fila_previews.setSpacing(20)

        columna_original = QVBoxLayout()
        columna_original.addWidget(QLabel("Original"))
        self.preview_original = PreviewLabel("Sin imagen")
        columna_original.addWidget(self.preview_original)
        fila_previews.addLayout(columna_original)

        columna_resultado = QVBoxLayout()
        columna_resultado.addWidget(QLabel("Resultado"))
        self.preview_resultado = PreviewLabel("Sin resultado", al_hacer_clic=self._abrir_ampliada)
        columna_resultado.addWidget(self.preview_resultado)
        fila_previews.addLayout(columna_resultado)

        layout_preview.addLayout(fila_previews)
        layout_raiz.addWidget(panel_preview)

        self._actualizar_disponibilidad_opciones(self.combo_metodo.currentText())

    def _actualizar_disponibilidad_opciones(self, metodo):
        self.combo_cierre.setEnabled(metodo == "Adaptativo")

    def dragEnterEvent(self, evento):
        if evento.mimeData().hasUrls():
            urls = evento.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith(EXTENSIONES_VALIDAS):
                evento.acceptProposedAction()

    def dropEvent(self, evento):
        ruta = evento.mimeData().urls()[0].toLocalFile()
        self._cargar_imagen(ruta)

    def seleccionar_imagen(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Selecciona un dibujo", self.carpeta_inicial, "Imágenes (*.jpg *.jpeg *.png)"
        )
        if ruta:
            self._cargar_imagen(ruta)

    def _cargar_imagen(self, ruta):
        self.ruta_imagen_entrada = ruta
        self.boton_procesar.setEnabled(True)
        self.boton_guardar.setEnabled(False)
        self.boton_aumentar.setEnabled(False)
        self.preview_resultado.set_image(None)
        self.etiqueta_estado.setText(f"Imagen seleccionada: {Path(ruta).name}")
        self.preview_original.set_image(QPixmap(ruta))

    def procesar(self):
        if not self.ruta_imagen_entrada:
            return

        metodo_ui = self.combo_metodo.currentText()
        metodo_backend = "threshold" if metodo_ui == "Adaptativo" else "ia"

        self.etiqueta_estado.setText(f"Procesando con '{metodo_ui}' (Esto puede tomar segundos)...")
        self.boton_procesar.setEnabled(False)
        self.boton_guardar.setEnabled(False)

        carpeta_temporal = tempfile.mkdtemp(prefix="vect_")
        nivel = self.NIVELES_CIERRE[self.combo_cierre.currentIndex()]

        self.hilo_procesamiento = HiloProcesamiento(
            self.ruta_imagen_entrada, carpeta_temporal, metodo_backend, nivel
        )
        self.hilo_procesamiento.finalizado.connect(self._al_finalizar_procesamiento)
        self.hilo_procesamiento.error.connect(self._al_error_procesamiento)
        self.hilo_procesamiento.start()

    def _al_finalizar_procesamiento(self, ruta_png, ruta_svg):
        self.ruta_png_resultado = ruta_png
        self.ruta_svg_resultado = ruta_svg

        compuesta = _componer_sobre_cuadros(ruta_png)
        qimagen = ImageQt(compuesta)
        self.preview_resultado.set_image(QPixmap.fromImage(qimagen))

        self.etiqueta_estado.setText("Listo. Puedes guardar el PNG y el SVG.")
        self.boton_procesar.setEnabled(True)
        self.boton_guardar.setEnabled(True)
        self.boton_aumentar.setEnabled(True)

    def _al_error_procesamiento(self, mensaje_error):
        QMessageBox.critical(self, "Error al procesar", mensaje_error)
        self.etiqueta_estado.setText("Ha ocurrido un error. Inténtalo de nuevo.")
        self.boton_procesar.setEnabled(True)

    def _abrir_ampliada(self):
        if self.ruta_png_resultado:
            VentanaAmpliada(self.ruta_png_resultado, self).exec()

    def aumentar_resolucion(self):
        if not self.ruta_png_resultado:
            return
        try:
            img = Image.open(self.ruta_png_resultado)
            img_ampliada = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
            img_ampliada.save(self.ruta_png_resultado)
            vectorizar_svg(self.ruta_png_resultado, self.ruta_svg_resultado)

            compuesta = _componer_sobre_cuadros(self.ruta_png_resultado)
            self.preview_resultado.set_image(QPixmap.fromImage(ImageQt(compuesta)))
            self.etiqueta_estado.setText("Resolución x2 aplicada.")
        except Exception as error:
            QMessageBox.critical(self, "Error", str(error))

    def guardar_resultados(self):
        if not self.ruta_png_resultado:
            return
        nombre_sugerido = Path(self.ruta_imagen_entrada).stem
        nombre_archivo, ok = QInputDialog.getText(self, "Guardar", "Nombre (sin extensión):", text=nombre_sugerido)
        if ok and nombre_archivo:
            carpeta = QFileDialog.getExistingDirectory(self, "Guardar en...", self.carpeta_inicial)
            if carpeta:
                shutil.copy(self.ruta_png_resultado, Path(carpeta) / f"{nombre_archivo}.png")
                shutil.copy(self.ruta_svg_resultado, Path(carpeta) / f"{nombre_archivo}.svg")
                self.etiqueta_estado.setText(f"Guardado en {carpeta}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())