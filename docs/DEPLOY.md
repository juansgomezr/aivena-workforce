# Guía de deploy — paso a paso

Esta guía es para que **tú** (no un dev experimentado) puedas deployar la app en Streamlit Cloud en menos de 10 minutos.

## Pre-requisitos

- [x] Cuenta de GitHub creada
- [x] Cuenta de Streamlit Cloud conectada a GitHub
- [x] API key de Anthropic guardada en lugar seguro

## Paso 1 — Subir el código a GitHub

### Opción A: vía la web de GitHub (más fácil, no requiere git CLI)

1. Ve a [github.com/new](https://github.com/new)
2. Repository name: `aivena-workforce`
3. Visibility: **Private** (recomendado — el código tiene tu nombre y la lógica de negocio)
4. **NO** marques "Add a README", "Add .gitignore", ni "Choose a license" — el repo viene con esos archivos.
5. Click "Create repository".
6. En la siguiente pantalla, click "uploading an existing file".
7. Descomprime el zip que te entregó Claude. Arrastra **todos los archivos y carpetas** del repo (no la carpeta `aivena-workforce/` en sí, solo el contenido) al área de upload.
8. Commit message: `Initial commit — Aivena Workforce MVP v0`
9. Click "Commit changes".

### Opción B: vía git CLI (si ya lo tienes instalado)

```bash
cd ~/Downloads/aivena-workforce  # o donde lo descomprimiste
git init
git add .
git commit -m "Initial commit — Aivena Workforce MVP v0"
git branch -M main
git remote add origin https://github.com/<TU-USUARIO>/aivena-workforce.git
git push -u origin main
```

## Paso 2 — Deploy en Streamlit Cloud

1. Ve a [share.streamlit.io](https://share.streamlit.io).
2. Click "Create app" (esquina superior derecha) → "Deploy a public app from GitHub".
3. Repository: selecciona `<TU-USUARIO>/aivena-workforce`
4. Branch: `main`
5. Main file path: `app.py`
6. App URL: deja la default o personaliza a `aivena-workforce` o similar.
7. **Antes de click Deploy**, click "Advanced settings…":
   - Python version: 3.11 o 3.12 (default está bien)
   - Secrets: pega esto, reemplazando con tu key real:
     ```toml
     ANTHROPIC_API_KEY = "sk-ant-api03-XXXXXXXXXXXXXXXXX"
     ```
   - Save.
8. Click "Deploy!".
9. Espera 2-4 minutos. Streamlit Cloud instala dependencias y arranca la app.

## Paso 3 — Verificar que funciona

Una vez que la app cargue:

1. Verás el sidebar con "Demo (datos sintéticos)" pre-seleccionado.
2. Click "Optimizar →".
3. Espera ~3-5 segundos. Deberías ver:
   - 4 KPIs arriba (ahorro semanal, ahorro anual, empleados regularizados, cobertura)
   - 4 tabs (Resumen ejecutivo, Análisis visual, Schedule semanal, Pregúntale a Aivena)
4. Click en cada tab para confirmar que renderean.
5. En "Pregúntale a Aivena", click uno de los botones de pregunta sugerida. Debería responder en ~3-5 segundos. Si dice "configura ANTHROPIC_API_KEY", revisa el paso 7 de arriba.

## Paso 4 — Compartir la URL

La URL será algo como:
- `https://aivena-workforce.streamlit.app` (si elegiste ese subdomain)
- `https://<usuario>-aivena-workforce-app-<hash>.streamlit.app` (si dejaste default)

Esa URL es **lo que entregas como "herramienta funcionando"** del reto:
- Se abre en cualquier navegador
- No requiere login
- Funciona en mobile (responsive)
- Cualquier evaluador puede subir un CSV propio y verla operar

## Errores comunes y cómo arreglarlos

### Error: "ModuleNotFoundError: No module named 'streamlit'"
- **Causa**: requirements.txt no se subió o está mal escrito.
- **Fix**: verifica que `requirements.txt` esté en el root del repo y contenga las 5 librerías.

### Error: "AttributeError: streamlit has no attribute 'chat_input'"
- **Causa**: Streamlit Cloud está usando una versión vieja.
- **Fix**: en `requirements.txt` cambia `streamlit>=1.31.0` a `streamlit==1.39.0`. Push, y Streamlit Cloud rebuildeará.

### La app deploya pero al hacer click en "Optimizar" no pasa nada
- **Causa**: probable error en el motor que está siendo silenciado.
- **Fix**: en Streamlit Cloud, click "Manage app" → "Logs". Verás el traceback. Cópialo y mándamelo.

### El brief ejecutivo dice "AI brief no disponible"
- **Causa**: API key no configurada o inválida.
- **Fix**: ve a Streamlit Cloud → tu app → "⋮" → "Settings" → "Secrets". Verifica que la key esté ahí y sea válida.

### El motor tarda más de 30 segundos
- **Causa**: greedy debería correr en <1s. Si tarda mucho es probable un loop infinito.
- **Fix**: revisa logs. Mándamelos.

## Para la demo del lunes

Antes de la demo:
1. **Pre-carga la app**: ábrela 30 minutos antes del meeting. Streamlit Cloud "duerme" apps inactivas; la primera carga puede tardar 30-60s.
2. **Corre una optimización**: deja la pestaña abierta con resultados ya cargados.
3. **Ten listo el zip del repo**: por si te piden ver el código en vivo.
4. **Practica las 3 preguntas Q&A**: validar que la latencia es aceptable (3-8s).
