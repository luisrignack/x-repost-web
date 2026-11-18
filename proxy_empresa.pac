// PAC de la red de la empresa (modo "Empresa").
// Tal como lo usa el usuario: dominios internos DIRECT, resto por el proxy.
// Nota: "HTTPS host" implica CONNECT por TLS al puerto 443 (es lo que declara
// este PAC). Si tu red exige otro esquema o puerto, usa el modo "Servidor
// manual" del panel con los valores reales de tu red.
function FindProxyForURL(url, host) {
    // Dominios de la empresa que deben omitir el proxy (conexión DIRECTA)
    if (dnsDomainIs(host, ".etecsa.cu") ||
        dnsDomainIs(host, "localhost") ||
        dnsDomainIs(host, ".fdc.com") ||
        dnsDomainIs(host, "pamarillas.cu") ||
        dnsDomainIs(host, ".etecsa.net") ||
        isPlainHostName(host)) {
        return "DIRECT";
    }

    // Proxy HTTPS para todo el tráfico web externo (HTTP y HTTPS)
    if (url.substring(0, 5) == "http:" || url.substring(0, 6) == "https:") {
        return "HTTPS internet.etecsa.cu";
    }

    return "DIRECT";
}
