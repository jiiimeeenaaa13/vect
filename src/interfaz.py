import re
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox,
    QFrame, QSizePolicy, QInputDialog, QDialog, QScrollArea
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
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


def _carpeta_inicial_selector():
    """
    Para Windows, intenta obtener la carpeta de usuario de WSL si se está ejecutando desde WSL.
    Si no, devuelve la carpeta de usuario normal.
    """
    try:
        resultado = subprocess.run(
            ["cmd.exe", "/c", "echo %USERPROFILE%"],
            capture_output=True, text=True, timeout=3
        )
        ruta_windows = resultado.stdout.strip()
        if ruta_windows:
            conversion = subprocess.run(
                ["wslpath", ruta_windows], capture_output=True, text=True, timeout=3
            )
            ruta_wsl = conversion.stdout.strip()
            if ruta_wsl and Path(ruta_wsl).exists():
                return ruta_wsl
    except Exception:
        pass
    return str(Path.home())


def _sanear_nombre_archivo(nombre):
    """Quitamos caracteres no válidos para nombres de archivo en Windows."""
    nombre = re.sub(r'[\\/:*?"<>|]', "", nombre).strip()
    return nombre


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
    """Solo se utiliza cuando ya está el resultado, para poder hacer clic y abrir la ventana ampliada."""
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
    """Ventan para ver el resultado más grande, con scroll si no cabe entero en pantalla."""
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
    DESCRIPCIONES_CIERRE = [
        "Detalle más fino",
        "Buen detalle global, más líneas",
    ]

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
        titulo.setWordWrap(True)
        layout_barra.addWidget(titulo)

        subtitulo = QLabel("Convierte tu dibujo escaneado en PNG y SVG con fondo transparente.")
        subtitulo.setObjectName("subtitulo")
        subtitulo.setWordWrap(True)
        layout_barra.addWidget(subtitulo)

        self.zona_arrastre = ZonaArrastre(self.seleccionar_imagen)
        layout_barra.addWidget(self.zona_arrastre)

        etiqueta_opciones = QLabel("Opciones")
        etiqueta_opciones.setObjectName("etiquetaSeccion")
        layout_barra.addWidget(etiqueta_opciones)

        self.combo_metodo = QComboBox()
        self.combo_metodo.addItems(["Adaptativo", "IA"])
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
        columna_original.setSpacing(6)
        columna_original.addWidget(self._titulo_preview("Original"))
        self.preview_original = PreviewLabel("Sin imagen")
        columna_original.addWidget(self.preview_original)
        fila_previews.addLayout(columna_original)

        columna_resultado = QVBoxLayout()
        columna_resultado.setSpacing(6)
        columna_resultado.addWidget(self._titulo_preview("Resultado"))
        self.preview_resultado = PreviewLabel("Sin resultado", al_hacer_clic=self._abrir_ampliada)
        columna_resultado.addWidget(self.preview_resultado)
        fila_previews.addLayout(columna_resultado)

        layout_preview.addLayout(fila_previews)
        layout_raiz.addWidget(panel_preview)

        self._actualizar_disponibilidad_opciones(self.combo_metodo.currentText())

    def _titulo_preview(self, texto):
        etiqueta = QLabel(texto)
        etiqueta.setStyleSheet("font-weight: 600; color: #444; font-size: 14px;")
        etiqueta.setFixedHeight(22)
        return etiqueta

    def _actualizar_disponibilidad_opciones(self, metodo):
        es_threshold = (metodo == "Adaptativo")
        self.combo_cierre.setEnabled(es_threshold)

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
            self, "Selecciona un dibujo", self.carpeta_inicial,
            "Imágenes (*.jpg *.jpeg *.png)"
        )
        if ruta:
            self._cargar_imagen(ruta)

    def _cargar_imagen(self, ruta):
        self.ruta_imagen_entrada = ruta
        self.boton_procesar.setEnabled(True)
        self.boton_guardar.setEnabled(False)
        self.boton_aumentar.setEnabled(False)
        self.boton_aumentar.setText("Aumentar resolución")

        self.preview_resultado.set_image(None)
        self.preview_resultado.setToolTip("")
        self.etiqueta_estado.setText(f"Imagen seleccionada: {Path(ruta).name}")

        pixmap = QPixmap(ruta)
        self.preview_original.set_image(pixmap)

    def procesar(self):
        if not self.ruta_imagen_entrada:
            return

        metodo_ui = self.combo_metodo.currentText()

        metodo_backend = "threshold" if metodo_ui == "Adaptativo" else "IA"

        self.etiqueta_estado.setText(f"Procesando con '{metodo_ui}'...")
        self.boton_procesar.setEnabled(False)
        self.boton_aumentar.setEnabled(False)
        self.boton_aumentar.setText("Aumentar resolución (x2)")
        QApplication.processEvents()

        try:
            carpeta_temporal = tempfile.mkdtemp(prefix="vect_")
            nivel = self.NIVELES_CIERRE[self.combo_cierre.currentIndex()]

            ruta_png, ruta_svg = procesar_img(
                self.ruta_imagen_entrada, carpeta_temporal, metodo_backend, tamano_cierre=nivel
            )

            self.ruta_png_resultado = ruta_png
            self.ruta_svg_resultado = ruta_svg

            compuesta = _componer_sobre_cuadros(ruta_png)
            qimagen = ImageQt(compuesta)
            pixmap = QPixmap.fromImage(qimagen)
            self.preview_resultado.set_image(pixmap)
            self.preview_resultado.setToolTip("Haz clic para ampliar")

            self.etiqueta_estado.setText("Listo. Puedes guardar el PNG y el SVG.")
            self.boton_guardar.setEnabled(True)
            self.boton_aumentar.setEnabled(True)

        except Exception as error:
            QMessageBox.critical(self, "Error al procesar", str(error))
            self.etiqueta_estado.setText("Ha ocurrido un error. Inténtalo de nuevo.")

        finally:
            self.boton_procesar.setEnabled(True)

    def _abrir_ampliada(self):
        if not self.ruta_png_resultado:
            return
        dialogo = VentanaAmpliada(self.ruta_png_resultado, self)
        dialogo.exec()

    def aumentar_resolucion(self):
        if not self.ruta_png_resultado:
            return

        self.etiqueta_estado.setText("Aumentando resolución (PNG y SVG)...")
        self.boton_aumentar.setEnabled(False)
        self.boton_guardar.setEnabled(False)
        QApplication.processEvents()

        try:
            img = Image.open(self.ruta_png_resultado)
            nuevo_tamano = (img.width * 2, img.height * 2)
            img_ampliada = img.resize(nuevo_tamano, Image.LANCZOS)
            img_ampliada.save(self.ruta_png_resultado)

            vectorizar_svg(self.ruta_png_resultado, self.ruta_svg_resultado)

            compuesta = _componer_sobre_cuadros(self.ruta_png_resultado)
            qimagen = ImageQt(compuesta)
            self.preview_resultado.set_image(QPixmap.fromImage(qimagen))

            self.boton_aumentar.setText("Resolución ya aumentada")
            self.etiqueta_estado.setText("Resolución x2 aplicada a PNG y SVG. Puedes guardar.")

        except Exception as error:
            QMessageBox.critical(self, "Error al aumentar resolución", str(error))
            self.etiqueta_estado.setText("Ocurrió un error al aumentar la resolución.")
            self.boton_aumentar.setEnabled(True)

        finally:
            self.boton_guardar.setEnabled(True)

    def guardar_resultados(self):
        if not self.ruta_png_resultado:
            return

        nombre_sugerido = Path(self.ruta_imagen_entrada).stem if self.ruta_imagen_entrada else "resultado"
        nombre_archivo, confirmado = QInputDialog.getText(
            self, "Nombre del archivo",
            "Nombre para guardar (sin extensión):",
            text=nombre_sugerido
        )
        if not confirmado:
            return

        nombre_archivo = _sanear_nombre_archivo(nombre_archivo)
        if not nombre_archivo:
            QMessageBox.warning(self, "Nombre no válido", "Escribe un nombre válido para el archivo.")
            return

        carpeta_destino = QFileDialog.getExistingDirectory(
            self, "Elige dónde guardar el PNG y el SVG",
            self.carpeta_inicial
        )
        if not carpeta_destino:
            return

        ruta_png_destino = Path(carpeta_destino) / f"{nombre_archivo}.png"
        ruta_svg_destino = Path(carpeta_destino) / f"{nombre_archivo}.svg"

        if ruta_png_destino.exists() or ruta_svg_destino.exists():
            respuesta = QMessageBox.question(
                self, "El archivo ya existe",
                f"Ya existe un archivo llamado '{nombre_archivo}' en esa carpeta.\n"
                "¿Quieres sobrescribirlo?",
                QMessageBox.Yes | QMessageBox.No
            )
            if respuesta != QMessageBox.Yes:
                return

        try:
            shutil.copy(self.ruta_png_resultado, ruta_png_destino)
            shutil.copy(self.ruta_svg_resultado, ruta_svg_destino)
            self.etiqueta_estado.setText(f"Guardado como '{nombre_archivo}' en: {carpeta_destino}")
        except Exception as error:
            QMessageBox.critical(self, "Error al guardar", str(error))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())