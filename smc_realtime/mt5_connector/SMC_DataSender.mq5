//+------------------------------------------------------------------+
//|                                              SMC_DataSender.mq5  |
//|                                     Smart Money Concepts Trading |
//|                                                                  |
//| Expert Advisor para enviar dados de candles para a API SMC       |
//| em tempo real via HTTP POST.                                     |
//+------------------------------------------------------------------+
#property copyright "SMC Trading"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- Parâmetros de entrada
input string   API_URL = "http://localhost:8000/candle";  // URL da API SMC
input string   SYMBOL_NAME = "";                           // Símbolo (vazio = atual)
input int      SEND_INTERVAL_SEC = 60;                     // Intervalo de envio (segundos)
input bool     SEND_ON_NEW_BAR = true;                     // Enviar apenas em nova barra
input bool     AUTO_TRADE = false;                         // Executar trades automaticamente
input double   LOT_SIZE = 1.0;                             // Tamanho do lote

//--- Variáveis globais
datetime lastBarTime = 0;
int httpTimeout = 5000;

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("SMC Data Sender inicializado");
    Print("API URL: ", API_URL);
    Print("Símbolo: ", SYMBOL_NAME == "" ? Symbol() : SYMBOL_NAME);
    
    // Verificar conexão com a API
    if(!TestAPIConnection())
    {
        Print("AVISO: Não foi possível conectar à API SMC");
    }
    
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("SMC Data Sender finalizado");
}

//+------------------------------------------------------------------+
//| Expert tick function                                               |
//+------------------------------------------------------------------+
void OnTick()
{
    string symbol = SYMBOL_NAME == "" ? Symbol() : SYMBOL_NAME;
    
    // Verificar se é uma nova barra
    datetime currentBarTime = iTime(symbol, PERIOD_M1, 0);
    
    if(SEND_ON_NEW_BAR && currentBarTime == lastBarTime)
        return;
    
    lastBarTime = currentBarTime;
    
    // Obter dados do candle anterior (completo)
    MqlRates rates[];
    if(CopyRates(symbol, PERIOD_M1, 1, 1, rates) != 1)
    {
        Print("Erro ao obter dados do candle");
        return;
    }
    
    // Enviar candle para a API
    string signals = SendCandleToAPI(symbol, rates[0]);
    
    // Processar sinais recebidos
    if(AUTO_TRADE && signals != "")
    {
        ProcessSignals(signals);
    }
}

//+------------------------------------------------------------------+
//| Envia candle para a API SMC                                        |
//+------------------------------------------------------------------+
string SendCandleToAPI(string symbol, MqlRates &rate)
{
    // Montar JSON
    string json = StringFormat(
        "{\"symbol\":\"%s\",\"time\":\"%s\",\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"volume\":%.0f}",
        symbol,
        TimeToString(rate.time, TIME_DATE|TIME_MINUTES|TIME_SECONDS),
        rate.open,
        rate.high,
        rate.low,
        rate.close,
        (double)rate.tick_volume
    );
    
    // Enviar via HTTP POST
    char post[];
    char result[];
    string headers = "Content-Type: application/json\r\n";
    
    StringToCharArray(json, post, 0, StringLen(json));
    
    int res = WebRequest(
        "POST",
        API_URL,
        headers,
        httpTimeout,
        post,
        result,
        headers
    );
    
    if(res == -1)
    {
        int error = GetLastError();
        Print("Erro HTTP: ", error);
        
        if(error == 4060)
        {
            Print("ERRO: URL não permitida. Adicione ", API_URL, " nas opções do MT5:");
            Print("Ferramentas -> Opções -> Expert Advisors -> Permitir WebRequest para URLs listadas");
        }
        
        return "";
    }
    
    string response = CharArrayToString(result);
    
    // Log se houver sinais
    if(StringFind(response, "entry_price") >= 0)
    {
        Print("Sinal recebido: ", response);
    }
    
    return response;
}

//+------------------------------------------------------------------+
//| Testa conexão com a API                                            |
//+------------------------------------------------------------------+
bool TestAPIConnection()
{
    char post[];
    char result[];
    string headers = "";
    
    // Testar endpoint de health check
    string testUrl = StringReplace(API_URL, "/candle", "/");
    
    int res = WebRequest(
        "GET",
        testUrl,
        headers,
        httpTimeout,
        post,
        result,
        headers
    );
    
    if(res == 200)
    {
        Print("Conexão com API OK");
        return true;
    }
    
    return false;
}

//+------------------------------------------------------------------+
//| Processa sinais recebidos da API                                   |
//+------------------------------------------------------------------+
void ProcessSignals(string signalsJson)
{
    // Parse simples do JSON (para sinais)
    // Em produção, use uma biblioteca JSON adequada
    
    if(StringFind(signalsJson, "BULLISH") >= 0)
    {
        // Extrair preços do JSON
        double entryPrice = ExtractPrice(signalsJson, "entry_price");
        double stopLoss = ExtractPrice(signalsJson, "stop_loss");
        double takeProfit = ExtractPrice(signalsJson, "take_profit");
        
        if(entryPrice > 0)
        {
            PlaceBuyLimit(entryPrice, stopLoss, takeProfit);
        }
    }
    else if(StringFind(signalsJson, "BEARISH") >= 0)
    {
        double entryPrice = ExtractPrice(signalsJson, "entry_price");
        double stopLoss = ExtractPrice(signalsJson, "stop_loss");
        double takeProfit = ExtractPrice(signalsJson, "take_profit");
        
        if(entryPrice > 0)
        {
            PlaceSellLimit(entryPrice, stopLoss, takeProfit);
        }
    }
}

//+------------------------------------------------------------------+
//| Extrai preço do JSON                                               |
//+------------------------------------------------------------------+
double ExtractPrice(string json, string key)
{
    int pos = StringFind(json, key);
    if(pos < 0) return 0;
    
    pos = StringFind(json, ":", pos);
    if(pos < 0) return 0;
    
    int endPos = StringFind(json, ",", pos);
    if(endPos < 0) endPos = StringFind(json, "}", pos);
    
    string value = StringSubstr(json, pos + 1, endPos - pos - 1);
    value = StringTrimLeft(StringTrimRight(value));
    
    return StringToDouble(value);
}

//+------------------------------------------------------------------+
//| Coloca ordem Buy Limit                                             |
//+------------------------------------------------------------------+
void PlaceBuyLimit(double price, double sl, double tp)
{
    CTrade trade;
    string symbol = SYMBOL_NAME == "" ? Symbol() : SYMBOL_NAME;
    
    if(trade.BuyLimit(LOT_SIZE, price, symbol, sl, tp, ORDER_TIME_GTC, 0, "SMC Signal"))
    {
        Print("Buy Limit colocada: ", price, " SL: ", sl, " TP: ", tp);
    }
    else
    {
        Print("Erro ao colocar Buy Limit: ", GetLastError());
    }
}

//+------------------------------------------------------------------+
//| Coloca ordem Sell Limit                                            |
//+------------------------------------------------------------------+
void PlaceSellLimit(double price, double sl, double tp)
{
    CTrade trade;
    string symbol = SYMBOL_NAME == "" ? Symbol() : SYMBOL_NAME;
    
    if(trade.SellLimit(LOT_SIZE, price, symbol, sl, tp, ORDER_TIME_GTC, 0, "SMC Signal"))
    {
        Print("Sell Limit colocada: ", price, " SL: ", sl, " TP: ", tp);
    }
    else
    {
        Print("Erro ao colocar Sell Limit: ", GetLastError());
    }
}

//+------------------------------------------------------------------+
//| Função auxiliar para substituir string                             |
//+------------------------------------------------------------------+
string StringReplace(string str, string find, string replace)
{
    string result = str;
    int pos = StringFind(result, find);
    if(pos >= 0)
    {
        result = StringSubstr(result, 0, pos) + replace + StringSubstr(result, pos + StringLen(find));
    }
    return result;
}
//+------------------------------------------------------------------+
