[app]

# Nombre que aparecerá en Android
title = Automatizador Android V1

# Nombre interno
package.name = automatizador

# Dominio de ejemplo
package.domain = org.yahir

# Directorio del proyecto
source.dir = .

# Archivos incluidos
source.include_exts = py,json,png,jpg,kv

# Versión
version = 1.0

# Dependencias Python
requirements = python3,kivy

# Orientación
orientation = portrait

# Pantalla completa
fullscreen = 0


# ============================================================
# ANDROID
# ============================================================

android.api = 35

android.minapi = 23

android.archs = arm64-v8a, armeabi-v7a

android.accept_sdk_license = True


# ============================================================
# NOMBRE DEL APK
# ============================================================

android.add_src =


# ============================================================
# ICONO
# ============================================================

# Si posteriormente quieres un icono:
#
# icon.filename = %(source.dir)s/data/icon.png


# ============================================================
# CONFIGURACIÓN DE BUILD
# ============================================================

[buildozer]

log_level = 2

warn_on_root = 1
