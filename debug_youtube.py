"""Diagnóstico da API do YouTube. Execute: python debug_youtube.py"""
import os, requests
from dotenv import load_dotenv
load_dotenv()

key = os.getenv('YOUTUBE_API_KEY')
ch  = os.getenv('YOUTUBE_CHANNEL_ID')
print(f"API Key: {key[:10]}..." if key else "❌ YOUTUBE_API_KEY não encontrada")
print(f"Channel: {ch}" if ch else "❌ YOUTUBE_CHANNEL_ID não encontrada")

base = 'https://www.googleapis.com/youtube/v3/search'

print("\n── Buscando live (eventType=live) ──")
r = requests.get(base, params={'part':'snippet','channelId':ch,'eventType':'live','type':'video','key':key}).json()
print(r)

print("\n── Buscando upcoming ──")
r2 = requests.get(base, params={'part':'snippet','channelId':ch,'eventType':'upcoming','type':'video','key':key}).json()
print(r2)

print("\n── Vídeos recentes ──")
r3 = requests.get(base, params={'part':'snippet','channelId':ch,'order':'date','type':'video','key':key}).json()
print(r3)
