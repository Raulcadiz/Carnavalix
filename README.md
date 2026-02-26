# 🎭 Carnavalix

> El Netflix del Carnaval de Cádiz — COAC por años, finales, callejeras y letras en un solo sitio.

## Inicio rápido

```bash
# 1. Clonar / ir al directorio
cd C:\user\FallaCarnaval

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
copy deploy\.env.example .env
# Edita .env con tu YOUTUBE_API_KEY y demás claves

# 5. Arrancar
python -m backend.main
```

Abre `http://localhost:5000` en el navegador.

## URLs principales

| URL | Descripción |
|-----|-------------|
| `/` | Catálogo principal (estilo Netflix) |
| `/player/<youtube_id>` | Reproductor + letras |
| `/chat` | Chat 24/7 con bot de carnaval |
| `/admin` | Panel de administración |
| `/api/videos/` | API REST de vídeos |
| `/api/letras/` | API REST de letras |
| `/api/votos/` | API REST de votos/ranking |

## Estructura del proyecto

```
FallaCarnaval/
├── backend/
│   ├── main.py              # App Flask + SocketIO
│   ├── config.py            # Configuración y env vars
│   ├── database.py          # SQLAlchemy + SQLite
│   ├── models.py            # Modelos: Video, Letra, Grupo, Voto, Chat
│   ├── routes/
│   │   ├── videos.py        # /api/videos/
│   │   ├── letras.py        # /api/letras/
│   │   ├── votos.py         # /api/votos/
│   │   ├── chat.py          # Chat WebSocket + bot
│   │   └── admin.py         # /admin/
│   └── services/
│       ├── youtube_scraper.py   # YouTube Data API v3
│       ├── odysee_uploader.py   # Backup en Odysee
│       └── scheduler.py         # Tareas automáticas
├── frontend/
│   ├── templates/           # HTML (Jinja2)
│   └── static/              # CSS, JS, imágenes
├── deploy/
│   ├── start.bat            # Arranque en Windows
│   ├── cloudflare-tunnel.yml
│   └── .env.example
├── data/                    # SQLite (generado automáticamente)
└── requirements.txt
```

## Despliegue en VPS Windows 11

### 1. Cloudflare Tunnel (HTTPS gratuito y permanente)
```bash
# Descargar cloudflared para Windows
# https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/

cloudflared tunnel login
cloudflared tunnel create carnavalix
cloudflared tunnel route dns carnavalix tudominio.noip.me
cloudflared tunnel --config deploy/cloudflare-tunnel.yml run
```

### 2. Arrancar como servicio de Windows (NSSM)
```bash
nssm install Carnavalix "C:\g3v3r\FallaCarnaval\venv\Scripts\python.exe" "-m backend.main"
nssm set CarnavalixAppDirectory "C:\user\FallaCarnaval"
nssm start Carnavalix
```

## Integrar letras de Carnaval-Letras

Desde el panel admin (`/admin`) → sección "Importar Letras":
1. Indica la ruta al archivo `.db` de tu instalación de Carnaval-Letras
2. Pulsa "Importar letras"
3. Las letras quedarán vinculadas a los vídeos por grupo y año

## PWA / APK

La plataforma es una **Progressive Web App**. En Android:
1. Abre `https://tudominio.noip.me` en Chrome
2. Menú → "Añadir a pantalla de inicio"
3. ¡Ya tienes la "app"! Sin App Store.

Para un APK real: usa [Capacitor](https://capacitorjs.com/) o [WebView APK](https://github.com/GoogleChrome/chrome-launcher).
