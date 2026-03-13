# Configuração de Rede - Backend Mobile

## Problema Resolvido

O app mobile estava tentando conectar em IPs incorretos (`10.0.0.198`, `10.0.2.2`, etc.) quando o backend está rodando na VPS com IP `10.0.0.4`.

## Solução Implementada

### 1. ApiClient.kt - Failover Automático

O app agora tenta conectar nesta ordem:

```kotlin
1. http://10.0.0.4:8000/  (VPS produção)
2. http://10.0.2.2:8000/  (Emulador Android -> host)
3. http://10.0.3.2:8000/  (Genymotion)
4. http://127.0.0.1:8000/ (localhost)
5. http://localhost:8000/ (localhost)
```

**Vantagem:** O app funciona automaticamente tanto na VPS quanto em desenvolvimento local.

### 2. build.gradle.kts - Default Atualizado

Default alterado de `http://10.0.2.2:8000/` para `http://10.0.0.4:8000/`

### 3. Arquivos Modificados

| Arquivo | Mudança |
|---------|---------|
| `android/app/src/main/java/.../ApiClient.kt` | Adicionado VPS IP como primeiro na lista de failover |
| `android/app/build.gradle.kts` | Default URL atualizado para VPS |
| `README.md` | Documentação atualizada |
| `build_app.sh` | Script de build com suporte a custom API URL |

## Como Usar

### Produção (VPS)

```bash
# Backend na VPS
cd ~/animecaos/mobile/backend
source .venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Build do app (não precisa configurar nada)
cd mobile/android
./build_app.sh debug
# ou
./build_app.sh release
```

App vai conectar automaticamente em `http://10.0.0.4:8000/`

### Desenvolvimento Local

**Opção A:** Build com parâmetro
```bash
cd mobile/android
./build_app.sh debug http://192.168.1.100:8000/
```

**Opção B:** `local.properties`
```properties
# mobile/android/local.properties
apiBaseUrl=http://192.168.1.100:8000/
```

**Opção C:** Failover automático
- Se backend está no seu PC, app vai tentar VPS primeiro
- Vai falhar, depois tentar `10.0.2.2` (emulador) ou `localhost`
- Funciona, mas pode demorar alguns segundos no failover

## Teste de Conectividade

### Na VPS:
```bash
# Verificar se backend está rodando
curl http://localhost:8000/health

# Deve retornar: {"status":"ok"}
```

### No App:
- Se conectar: ✅ Funcionando
- Se falhar: Verificar logs do app e backend

### Debug de Rede:

```bash
# Na VPS, verificar se porta está ouvindo
netstat -tlnp | grep 8000

# Verificar IP da VPS
hostname -I
# Deve mostrar: 10.0.0.4

# Testar firewall
sudo iptables -L -n | grep 8000
# Se estiver bloqueado:
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
```

## Configuração do Firewall

### Ubuntu/Debian:
```bash
# Se usar ufw
sudo ufw allow 8000/tcp
sudo ufw reload
```

### CentOS/RHEL:
```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### Manual (iptables):
```bash
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
sudo iptables-save > /etc/iptables/rules.v4
```

## Resumo

| Cenário | IP do Backend | Configuração no App |
|---------|---------------|---------------------|
| VPS Produção | `10.0.0.4:8000` | Automático (default) |
| Dev no PC + Emulador | `10.0.2.2:8000` | Automático (failover) |
| Dev no PC + Dispositivo Físico | `192.168.X.X:8000` | Build com `-PapiBaseUrl` |
| Dev no PC + Emulador (rápido) | `localhost:8000` | `adb reverse tcp:8000 tcp:8000` |

## Troubleshooting

### App não conecta

1. Verificar se backend está rodando:
   ```bash
   curl http://10.0.0.4:8000/health
   ```

2. Verificar logs do backend:
   ```bash
   # Deve mostrar:
   # INFO: Uvicorn running on http://0.0.0.0:8000
   ```

3. Verificar firewall da VPS:
   ```bash
   sudo iptables -L -n | grep 8000
   ```

4. Verificar se app está usando IP correto:
   - Olhar logs do app (Logcat)
   - Deve mostrar tentativa em `10.0.0.4:8000`

### Backend não inicia

```bash
# Verificar se porta já está em uso
netstat -tlnp | grep 8000

# Matar processo se necessário
kill <PID>

# Reiniciar
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Próximos Passos

1. ✅ Backend com patches aplicados (selenium + cloudscraper)
2. ✅ App configurado para VPS IP
3. 🔄 Testar conexão do app
4. 🔄 Testar busca de animes
5. 🔄 Testar playback de vídeo

---

**Atualizado:** 2026-03-13  
**Status:** ✅ Configuração de rede concluída
