import xbmcgui
import xbmcplugin
import xbmcaddon
import os
import sys
import urllib.parse
import requests
import json
from datetime import datetime

# Obtener la ruta de la carpeta raíz del addon y construir la ruta al archivo M3U local
addon = xbmcaddon.Addon()
addon_path = addon.getAddonInfo('path')

# URLs remotas para la lista de canales en GitHub y lista de eventos JSON
M3U_REMOTE_URL = "https://raw.githubusercontent.com/Tbleo1189/Senku-Tv/refs/heads/main/lista1.m3u"
EVENTOS_JSON_URL = "https://raw.githubusercontent.com/Tbleo1189/Senku-Tv/refs/heads/main/eventos.json"

# Identificador del add-on en ejecución
ADDON_HANDLE = int(sys.argv[1])

def cargar_lista_m3u(ruta_m3u, es_remota=False):
    """Carga y parsea una lista M3U para extraer los nombres y enlaces AceStream."""
    canales = []
    try:
        if es_remota:
            # Cargar contenido desde una URL remota
            xbmc.log(f"Cargando lista remota desde {ruta_m3u}", xbmc.LOGINFO)
            response = requests.get(ruta_m3u, timeout=10)
            response.raise_for_status()
            contenido_m3u = response.text
        else:
            # Cargar contenido desde un archivo local
            xbmc.log("Cargando lista local M3U desde archivo", xbmc.LOGINFO)
            with open(ruta_m3u, 'r', encoding='utf-8') as file:
                contenido_m3u = file.read()
        
        nombre_canal = None
        for linea in contenido_m3u.splitlines():
            if linea.startswith("#EXTINF"):
                nombre_canal = linea.split(",")[-1].strip()
            elif linea.startswith("acestream://"):
                acestream_id = linea.split("acestream://")[-1].strip()
                if nombre_canal:
                    canales.append({"name": nombre_canal, "id": acestream_id})
                    nombre_canal = None  # Restablecer para el próximo canal

        if not canales:
            xbmcgui.Dialog().notification("Error", "La lista M3U no contiene canales válidos", xbmcgui.NOTIFICATION_ERROR)
            xbmc.log("La lista M3U no contiene canales válidos", xbmc.LOGERROR)
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().notification("Error", f"Error al cargar la lista remota: {e}", xbmcgui.NOTIFICATION_ERROR)
        xbmc.log(f"Error al cargar la lista remota: {e}", xbmc.LOGERROR)
    except Exception as e:
        xbmcgui.Dialog().notification("Error", f"Error al cargar la lista M3U: {e}", xbmcgui.NOTIFICATION_ERROR)
        xbmc.log(f"Error general al cargar la lista M3U: {e}", xbmc.LOGERROR)
    
    return canales

def cargar_lista_eventos_json(url_json):
    """Carga y parsea una lista de eventos JSON."""
    eventos = []
    try:
        response = requests.get(url_json, timeout=10)
        response.raise_for_status()
        eventos_json = response.json()

        for evento in eventos_json:
            if "name" in evento and "acestream_id" in evento and "start_time" in evento:
                eventos.append({
                    "name": evento["name"], 
                    "acestream_id": evento["acestream_id"], 
                    "start_time": evento["start_time"], 
                    "description": evento.get("description", "")
                })
        
        if not eventos:
            xbmcgui.Dialog().notification("Error", "La lista JSON no contiene eventos válidos", xbmcgui.NOTIFICATION_ERROR)
            xbmc.log("La lista JSON no contiene eventos válidos", xbmc.LOGERROR)
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().notification("Error", f"Error al cargar la lista JSON: {e}", xbmcgui.NOTIFICATION_ERROR)
        xbmc.log(f"Error al cargar la lista JSON: {e}", xbmc.LOGERROR)
    except Exception as e:
        xbmcgui.Dialog().notification("Error", f"Error al procesar JSON: {e}", xbmcgui.NOTIFICATION_ERROR)
        xbmc.log(f"Error general al procesar JSON: {e}", xbmc.LOGERROR)
    
    return eventos

def asociar_eventos_a_canales(canales, eventos):
    """Asocia los eventos con los canales usando el ID de AceStream."""
    eventos_asociados = []
    for evento in eventos:
        for canal in canales:
            if evento['acestream_id'] == canal['id']:  # Coincidir por el ID de AceStream
                evento['canal_name'] = canal['name']  # Añadir el nombre del canal al evento
                eventos_asociados.append(evento)
                break  # Ya encontramos la coincidencia, pasamos al siguiente evento
    
    return eventos_asociados

def list_events():
    """Muestra los eventos cargados desde el archivo JSON, asociados a canales."""
    canales = cargar_lista_m3u(M3U_REMOTE_URL, es_remota=True)  # Cargar la lista remota de canales
    eventos = cargar_lista_eventos_json(EVENTOS_JSON_URL)  # Cargar los eventos
    eventos_background_image = os.path.join(addon_path, 'resources', 'fondos', 'eventos_background.jpg')
    
    # Asociar los eventos a los canales
    eventos_asociados = asociar_eventos_a_canales(canales, eventos)

    if not eventos_asociados:
        xbmcgui.Dialog().notification("Error", "No hay eventos válidos asociados a canales", xbmcgui.NOTIFICATION_ERROR)
        return

    for evento in eventos_asociados:
        nombre_evento = evento.get("name", "Evento sin nombre")
        start_time_formatted = evento.get("start_time", "Hora no disponible")  # Usar la hora tal cual está en el JSON
        description = evento.get('description', 'Descripción no disponible')
        canal_name = evento.get('canal_name', 'Canal no disponible')  # Obtener el nombre del canal
        
        # Crear un ítem de lista para cada evento con un punto antes del nombre
        label_evento = f"• {nombre_evento} - Canal: {canal_name} ({start_time_formatted})"
        list_item = xbmcgui.ListItem(label=label_evento)
        list_item.setArt({"fanart": eventos_background_image})
        list_item.setInfo('video', {
            'title': nombre_evento,
            'plot': f"{description}\nCanal: {canal_name}",
        })
        
        url = f"{sys.argv[0]}?action=play_acestream&id={evento['acestream_id']}"
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=False)
    
    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def play_acestream_link(acestream_id):
    """Reproduce un enlace AceStream utilizando Horus."""
    encoded_id = urllib.parse.quote_plus(acestream_id)
    command = f'RunPlugin(plugin://script.module.horus/?action=play&id={encoded_id})'
    xbmc.executebuiltin(command)

def list_acestream_channels(canales):
    """Muestra un menú con la lista de canales AceStream cargados desde el M3U."""
    if not canales:
        xbmcgui.Dialog().notification("Error", "No hay canales disponibles", xbmcgui.NOTIFICATION_ERROR)
        return

    # Imagen de fondo para la lista de canales
    channels_background_image = os.path.join(addon_path, 'resources', 'fondos', 'channels_background.jpg')

    for channel in canales:
        list_item = xbmcgui.ListItem(label=channel['name'])
        list_item.setInfo('video', {'title': channel['name']})
        list_item.setArt({"fanart": channels_background_image})  # Imagen de fondo para cada canal
        
        # URL para reproducir el canal al hacer clic
        url = f"{sys.argv[0]}?action=play_acestream&id={channel['id']}"
        
        # Agrega el canal a la lista de visualización en Kodi
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=list_item, isFolder=False)
    
    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def mostrar_menus_principales():
    """Muestra los menús principales para elegir entre la lista remota o eventos, con imagen de fondo."""
    # Ruta de la imagen de fondo del menú principal
    menu_background_image = os.path.join(addon_path, 'resources', 'fondos', 'background.jpg')
    
    # Configura el fondo de cada elemento de menú
    list_item_remote = xbmcgui.ListItem(label="Canales Actualizados")
    list_item_remote.setArt({"fanart": menu_background_image})
    url_remote = f"{sys.argv[0]}?action=list_remote_channels"
    xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url_remote, listitem=list_item_remote, isFolder=True)
    
    list_item_events = xbmcgui.ListItem(label="Ver Directos")
    list_item_events.setArt({"fanart": menu_background_image})
    url_events = f"{sys.argv[0]}?action=list_events"
    xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url_events, listitem=list_item_events, isFolder=True)
    
    xbmcplugin.endOfDirectory(ADDON_HANDLE)

if __name__ == "__main__":
    # Leer los parámetros de la URL
    params = urllib.parse.parse_qs(sys.argv[2][1:])
    action = params.get("action", [None])[0]
    acestream_id = params.get("id", [None])[0]

    if action == "play_acestream" and acestream_id:
        play_acestream_link(acestream_id)
    elif action == "list_remote_channels":
        canales_remotos = cargar_lista_m3u(M3U_REMOTE_URL, es_remota=True)
        list_acestream_channels(canales_remotos)
    elif action == "list_events":
        list_events()  # Llamar a list_events para mostrar eventos
    else:
        mostrar_menus_principales()
