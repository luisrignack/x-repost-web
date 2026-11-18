// PAC "Automático": decide según estemos en la red de la empresa.
// Si el nombre del proxy resuelve (DNS interno), se usa; si no, DIRECT.
// Requiere validar en ambos entornos: con VPN el DNS puede resolver en casa.
function FindProxyForURL(url, host) {
    if (isPlainHostName(host) ||
        dnsDomainIs(host, ".etecsa.cu") ||
        dnsDomainIs(host, ".etecsa.net") ||
        dnsDomainIs(host, ".fdc.com") ||
        dnsDomainIs(host, "pamarillas.cu")) {
        return "DIRECT";
    }

    if (url.substring(0, 5) == "http:" || url.substring(0, 6) == "https:") {
        var proxyIp = dnsResolve("internet.etecsa.cu");
        if (proxyIp) {
            return "HTTPS internet.etecsa.cu";
        }
        return "DIRECT";
    }

    return "DIRECT";
}
