"""Agenda no Buffer os 5 posts de um dia do Tobest Quiz (07h, 11h30, 15h, 19h, 21h30, Brasília).

Uso: python3 publicar_quiz.py 2026-11-11 [--teste]
     python3 publicar_quiz.py amanha
Dia N = data - 10/11/2026 (11/11 = Dia 1 = vídeos 0001 a 0005; Dia 2 = 0006 a 0010; ...).
Chave: BUFFER_API_KEY_QUIZ (variável de ambiente, nunca no código). Não usa a chave da café nem da Pausa.
Vídeos: <BASE>/videos/NNNN.mp4 ; legendas: legendas.json (mesma pasta do repo).
"""
import json, os, sys, datetime, urllib.request

API = "https://api.buffer.com"
BASE = os.environ.get("QUIZ_VIDEO_BASE", "https://raw.githubusercontent.com/rogeriosuavinha-arch/tobest-quiz-videos/main")
LEGENDAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "legendas.json")
HORAS = ["07:00", "11:30", "15:00", "19:00", "21:30"]
BRT = datetime.timezone(datetime.timedelta(hours=-3))
INICIO = datetime.date(2026, 11, 10)
CANAL_NOME = "tobestquiz"


def gql(query, variables=None):
    req = urllib.request.Request(API, json.dumps({"query": query, "variables": variables or {}}).encode(),
                                 {"Content-Type": "application/json",
                                  "Authorization": f"Bearer {os.environ['BUFFER_API_KEY_QUIZ']}"})
    resp = json.load(urllib.request.urlopen(req, timeout=60))
    if resp.get("errors"):
        raise SystemExit(f"Erro do Buffer: {resp['errors']}")
    return resp["data"]


def canal():
    achados = []
    for org in gql("query { account { organizations { id } } }")["account"]["organizations"]:
        q = "query($o: OrganizationId!) { channels(input: {organizationId: $o}) { id service name } }"
        for c in gql(q, {"o": org["id"]})["channels"]:
            achados.append(f"{c['service']}:{c['name']}")
            if c["service"].lower() == "tiktok" and c["name"].lstrip("@") == CANAL_NOME:
                return org["id"], c["id"]
    raise SystemExit(f"Canal {CANAL_NOME} não encontrado nesse Buffer. Canais: {achados}")


def ja_agendados(org, cid, data):
    q = "query($i: PostsInput!) { posts(first: 50, input: $i) { edges { node { dueAt } } } }"
    i = {"organizationId": org, "filter": {"channelIds": [cid],
         "dueAt": {"start": f"{data}T00:00:00-03:00", "end": f"{data}T23:59:59-03:00"}}}
    return {f"{datetime.datetime.fromisoformat(e['node']['dueAt'].replace('Z', '+00:00')).astimezone(BRT):%H:%M}"
            for e in gql(q, {"i": i})["posts"]["edges"]}


CRIAR = """mutation($i: CreatePostInput!) { createPost(input: $i) {
  ... on PostActionSuccess { post { id dueAt } } ... on MutationError { message } } }"""


def existe(url):
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30); return True
    except Exception:
        return False


def main():
    hoje = datetime.datetime.now(BRT).date()
    data = hoje + datetime.timedelta(1) if sys.argv[1] == "amanha" else datetime.date.fromisoformat(sys.argv[1])
    teste = "--teste" in sys.argv
    dia = (data - INICIO).days
    if dia < 1:
        raise SystemExit("Data antes da estreia (11/11/2026).")
    L = json.load(open(LEGENDAS))
    org, cid = (None, None) if teste else canal()
    feitos = set() if teste else ja_agendados(org, cid, data)
    agora = datetime.datetime.now(BRT)
    falhas = 0
    for k, hora in enumerate(HORAS):
        num = f"{(dia - 1) * 5 + k + 1:04d}"
        due = datetime.datetime.fromisoformat(f"{data}T{hora}:00-03:00")
        if due <= agora + datetime.timedelta(minutes=10):
            print(hora, num, "horário já passou, pulando"); continue
        if hora in feitos:
            print(hora, num, "já agendado, pulando"); continue
        if num not in L:
            print(hora, num, "sem legenda"); falhas += 1; continue
        url = f"{BASE}/videos/{num}.mp4"
        entrada = {"channelId": cid, "text": L[num]["legenda"], "schedulingType": "automatic",
                   "mode": "customScheduled", "needsApproval": False, "dueAt": due.isoformat(),
                   "assets": [{"video": {"url": url}}]}
        if teste:
            print(json.dumps(entrada, ensure_ascii=False)); continue
        if not existe(url):
            print(hora, num, "vídeo não encontrado:", url); falhas += 1; continue
        r = gql(CRIAR, {"i": entrada})["createPost"]
        if not r.get("post"):
            falhas += 1
        print(hora, num, r.get("post") or r.get("message"))
    if falhas:
        raise SystemExit(f"{falhas} post(s) não agendado(s). Pode faltar subir o próximo lote de vídeos.")


if __name__ == "__main__":
    main()
