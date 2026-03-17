# Relatório de Auditoria: Engine SMC (Smart Money Concepts)

**Data:** 17 de Março de 2026  
**Repositório:** `thiagolealg/ultimate_SMC`  
**Autor:** Manus AI

## 1. Resumo Executivo

A pedido do usuário, foi realizada uma auditoria completa na engine de Order Blocks do repositório `ultimate_SMC`. O objetivo principal foi verificar a existência de excesso de Order Blocks (OBs) sendo gerados e armazenados, bem como analisar possíveis problemas de performance.

A análise confirmou **graves problemas de gerenciamento de memória e lógica de acúmulo infinito**, afetando tanto as versões de backtest (`smc_engine_v2.py` e `smc_engine_v3.py`) quanto a versão de produção (`smc_realtime/app/smc_engine.py`). A engine não implementa nenhuma rotina de limpeza (garbage collection) para remover OBs antigos ou mitigados, resultando em crescimento linear do consumo de memória e degradação progressiva da performance (aumento do tempo de processamento por candle).

Além disso, foram identificadas divergências críticas entre a lógica da versão de backtest e a versão em tempo real, que causam a geração de múltiplos sinais repetidos em produção.

## 2. Diagnóstico de Problemas Críticos

### 2.1. Acúmulo Infinito de Order Blocks (Memory Leak Lógico)

A engine sofre de um problema crítico de retenção de dados. Quando um Order Block é detectado, ele é adicionado à lista `active_obs` (ou `order_blocks` na versão realtime). No entanto, **nenhuma rotina remove esses OBs da lista**, mesmo após serem mitigados (invalidados) pelo preço.

*   **Evidência no Código:** Nas funções `_check_ob_mitigation`, os OBs mitigados têm a flag `ob.mitigated = True` ativada, mas não há nenhuma instrução `remove()`, `pop()` ou recriação da lista filtrando os inativos.
*   **Impacto Prático:** Em um teste com apenas 222 candles (aproximadamente 3,7 horas em M1), 70% da lista de OBs ativos já era composta por "lixo" (OBs mitigados).
*   **Projeção:** Para 1 ano de pregão (aprox. 120.960 candles), a engine acumulará mais de 5.400 Order Blocks na memória. Como a função de verificação de mitigação itera sobre *todos* os OBs da lista a cada novo candle, a complexidade computacional passa de O(1) para O(N), causando travamentos em sessões longas.

### 2.2. Geração de Sinais Repetidos em Produção (Realtime)

A versão em produção (`smc_realtime/app/smc_engine.py`) possui uma falha grave na geração de sinais, causando flood de alertas ou ordens duplicadas.

*   **Evidência no Código:** O método `_generate_signals()` itera sobre *todos* os OBs não mitigados a cada novo candle. Ele tenta evitar duplicatas usando `_has_pending_order_for_ob()`, mas se a ordem anterior foi preenchida ou fechada, essa função retorna `False`, e a engine gera **um novo sinal para o mesmo Order Block**.
*   **Impacto:** Um único OB válido pode gerar dezenas de sinais consecutivos até que o preço o atravesse completamente e ele seja marcado como mitigado.

### 2.3. Acúmulo Infinito de Arrays OHLCV e Swings

As versões V2 e V3 armazenam todo o histórico de preços (Open, High, Low, Close, Volume) e todos os pontos de Swing High/Low em listas Python padrão, sem limite máximo.

*   **Evidência:** `self.opens.append(o)`, `self.swing_highs.append(...)`.
*   **Impacto:** Embora listas de floats não consumam tanta memória quanto objetos complexos (1 milhão de candles = ~38 MB), o acúmulo das tuplas de swings e outros padrões (FVGs, BOS, CHoCH limitados a 50) demonstra uma arquitetura não otimizada para operação contínua 24/7. A versão `smc_realtime` corrige parcialmente o OHLCV usando `deque(maxlen=5000)`, mas não corrige o acúmulo da lista de OBs.

## 3. Divergências Lógicas entre Backtest e Produção

Foi constatado que a versão de produção (Realtime) não executa exatamente a mesma lógica validada nos backtests (V3). As principais divergências que comprometem a confiabilidade da estratégia são:

| Funcionalidade | V3 (Backtest Validado) | Realtime (Produção) | Impacto |
| :--- | :--- | :--- | :--- |
| **Limites do OB** | Usa `max/min(open, close)` (corpo do candle) | Usa `high/low` (inclui sombras) | OBs na produção são muito maiores, gerando SLs maiores e distorcendo a taxa de acerto. |
| **Expiração de Ordens** | Ordens expiram após 150 candles | **Sem expiração** | Ordens pendentes ficam "penduradas" para sempre na memória. |
| **Proteção de Fill** | Cancela entrada se o candle de fill ultrapassar o OB inteiro | **Sem proteção** | Pode entrar em trades onde o OB já foi completamente destruído no mesmo minuto. |
| **Geração de Sinal** | Apenas no momento da detecção do OB | A cada candle para todos os OBs ativos | Sinais repetidos e falsas entradas. |

## 4. Recomendações e Soluções

Para corrigir o excesso de Order Blocks e os problemas de performance, as seguintes alterações devem ser implementadas no código:

### 4.1. Implementar Garbage Collection de Order Blocks

Em todas as engines (`smc_engine_v3.py` e `smc_realtime/app/smc_engine.py`), modifique as funções de mitigação para limpar a lista ativamente.

**Correção sugerida (Exemplo para V3):**
```python
def _check_ob_mitigation(self, idx: int):
    h = self.highs[idx]
    l = self.lows[idx]
    
    # Nova lista apenas com OBs que sobrevivem
    remaining_obs = []
    
    for ob in self.active_obs:
        if ob.mitigated:
            continue
            
        if idx <= ob.confirmation_index:
            remaining_obs.append(ob)
            continue
            
        is_mitigated_now = False
        if ob.direction == SignalDirection.BULLISH:
            if l <= ob.bottom:
                is_mitigated_now = True
        else:
            if h >= ob.top:
                is_mitigated_now = True
                
        if is_mitigated_now:
            ob.mitigated = True
            ob.mitigated_index = idx
            # Opcional: salvar em uma lista separada de histórico se necessário
        else:
            remaining_obs.append(ob)
            
    # Substituir a lista antiga
    self.active_obs = remaining_obs
```

### 4.2. Corrigir a Geração Repetida de Sinais na Realtime

Na `smc_realtime/app/smc_engine.py`, adicione uma flag no objeto `OrderBlock` para rastrear se ele já gerou um sinal, independente do status da ordem.

**Correção sugerida:**
1. Adicionar `signal_generated: bool = False` na dataclass `OrderBlock`.
2. No `_generate_signals`, adicionar a verificação:
```python
if getattr(ob, 'signal_generated', False):
    continue
# ... código de geração do sinal ...
ob.signal_generated = True
```

### 4.3. Unificar Lógica de Limites do OB

Para garantir que a produção tenha os mesmos resultados do backtest, a engine Realtime deve adotar a mesma definição de limites do OB usada na V3 (apenas o corpo do candle, não as sombras).

**Correção em `smc_realtime/app/smc_engine.py`:**
Substituir:
```python
top=candle['high'],
bottom=candle['low'],
```
Por:
```python
top=max(candle['open'], candle['close']),
bottom=min(candle['open'], candle['close']),
```

### 4.4. Limitar o Histórico de Swings

Nas versões V2 e V3, substituir as listas nativas por `collections.deque(maxlen=1000)` para `swing_highs` e `swing_lows`, garantindo que apenas os topos e fundos relevantes para o contexto atual sejam mantidos em memória, evitando vazamentos em execuções de longo prazo.
