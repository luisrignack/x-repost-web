// PAC de la red de la empresa (modo "Empresa").
// Tal como lo usa el usuario: dominios internos DIRECT, resto por el proxy.
// OJO: "HTTPS host" implica CONNECT por TLS al puerto 443. Si tu proxy es
// HTTP en 3128, usa el modo "Servidor manual" con esquema http en el panel.
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
