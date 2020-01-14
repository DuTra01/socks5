# Proxy socks5
1. Versao: 0.1
2. Autor: Glemison Dutra

# Recursos
1. Nenhuma dependência externa além das bibliotecas padrão do python

### Modo de instalação 
```
wget https://raw.githubusercontent.com/GlEmYsSoN444/socks5/master/socks5.py
```

### Modo de execução
```
python3 socks5.py
```

### Execute em segundo plano

```
apt-get install screen -y
screen -S socks5 -dm python3 socks5.py >> log.txt
```
(Registro de logs em `log.txt`)

### Encerre execução em segundo plano
```
screen -S socks5 -X quit
```
(Use apenas no debian e seus derivados)

