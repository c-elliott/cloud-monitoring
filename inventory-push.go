// https://github.com/c-elliott

// A monitoring agent implemented in a push model, to submit local
// system inventory and metrics to an API via HTTPS POST with
// basic auth (user,pass) token and SSL CA verification. 

package main

import (
    "bytes"
    "encoding/json"
    "io/ioutil"
    "fmt"
    "os"
    "os/exec"
    "net/http"
    "strings"
    "strconv"
    "github.com/marcsauter/single"
    "time"
    "crypto/x509"
    "crypto/tls"
)

var (
    name = "inventory-push"
    version = "1.0"
    authuser = "push"
    authpass = "NWVkN2Q2NGE2YjIxM2E3MjhjYjZZTIwNzBkZTZjYzI4NWZj"
    token = "ZTM0Zjk0YjFkZmZhQ4NzM5YzMwM2VmMjY2ZTgwYTRjZTczZWY5"
    cafile = "/opt/inventory-push/ssl/ca.pem"
    apiurl = "https://yourdomain.com/api"
)

func currentUID() string {
    if id := os.Getuid(); id >= 0 {
        return strconv.Itoa(id)
    }
    return ""
}

func main() {

    // Print program name
    fmt.Print("[", name, "]\n")

    // Exit program if not running as root
    if currentUID() != strconv.Itoa(0) {
        fmt.Print("NOT-ROOT\n")
        os.Exit(0)
    }

    // Locking mechanism to ensure single instance of program
    s := single.New(name)
    s.Lock()
    defer s.Unlock()

    // Here we read in a CA certificate and configure our own transport for the http client
    // This is because our CA is not trusted by the local system
    cacert, err := ioutil.ReadFile(cafile)
    if err != nil {
        fmt.Print("MISSING-CAFILE\n")
        os.Exit(0)
    }
    cacertpool :=x509.NewCertPool()
    cacertpool.AppendCertsFromPEM(cacert)
    tlsConfig := &tls.Config{
        RootCAs: cacertpool,
    }
    tlsConfig.BuildNameToCertificate()
    transport := &http.Transport{TLSClientConfig: tlsConfig}

    // Calculate epoch timestamp in nanoseconds for metrics
    timestamp_res := strconv.Itoa(int(time.Now().UnixNano()))

    // Metrics ordered approx fastest>slowest for accuracy
    loadavg_run, _ := exec.Command("bash", "-c", "awk '{ print $1,$2,$3 }' /proc/loadavg").Output()
    loadavg_res := strings.TrimSuffix(string(loadavg_run), "\n")
    memtotal_run, _ := exec.Command("bash", "-c", "awk '/MemTotal/ { print $2 }' /proc/meminfo").Output()
    memtotal_res := strings.TrimSuffix(string(memtotal_run), "\n")
    memfree_run, _ := exec.Command("bash", "-c", "awk '/MemFree/ { print $2 }' /proc/meminfo").Output()
    memfree_res := strings.TrimSuffix(string(memfree_run), "\n")
    membuffers_run, _ := exec.Command("bash", "-c", "awk '/Buffers/ { print $2 }' /proc/meminfo").Output()
    membuffers_res := strings.TrimSuffix(string(membuffers_run), "\n")
    memcached_run, _ := exec.Command("bash", "-c", "awk '/^Cached/ { print $2 }' /proc/meminfo").Output()
    memcached_res := strings.TrimSuffix(string(memcached_run), "\n")
    memavailable_run, _ := exec.Command("bash", "-c", "awk '/MemAvailable/ { print $2 }' /proc/meminfo").Output()
    memavailable_res := strings.TrimSuffix(string(memavailable_run), "\n")
    swaptotal_run, _ := exec.Command("bash", "-c", "awk '/SwapTotal/ { print $2 }' /proc/meminfo").Output()
    swaptotal_res := strings.TrimSuffix(string(swaptotal_run), "\n")
    swapfree_run, _ := exec.Command("bash", "-c", "awk '/SwapFree/ { print $2 }' /proc/meminfo").Output()
    swapfree_res := strings.TrimSuffix(string(swapfree_run), "\n")
    netsar_run, _ := exec.Command("bash", "-c", "export LC_TIME='POSIX' ; sar -n DEV 1 1 | awk '!/Average/ && !/IFACE/ { if(NR!=1 && NF!=0) {print $2\"|\"$3\"|\"$4\"|\"$5\"|\"$6 }}' | xargs").Output()
    netsar_res := strings.TrimSuffix(string(netsar_run), "\n")
    mpstat_run, _ := exec.Command("bash", "-c", "export LC_TIME='POSIX' ; mpstat -P ALL 1 1 | awk '!/Average/ {if (NR!=1 && NR!=2 && NR!=3 && NR!=4 && NF!=0) { print $2\"|\"$3\"|\"$4\"|\"$5\"|\"$6\"|\"$7\"|\"$8\"|\"$9\"|\"$11 }}' | xargs").Output()
    mpstat_res := strings.TrimSuffix(string(mpstat_run), "\n")
    tcpnum_run, _ := exec.Command("bash", "-c", "wc -l /proc/net/tcp | awk '{ print $1 }'").Output()
    tcpnum_res := strings.TrimSuffix(string(tcpnum_run), "\n")
    udpnum_run, _ := exec.Command("bash", "-c", "wc -l /proc/net/udp | awk '{ print $1 }'").Output()
    udpnum_res := strings.TrimSuffix(string(udpnum_run), "\n")
    numprocs_run, _ := exec.Command("bash", "-c", "ps -Al | wc -l").Output()
    numprocs_res := strings.TrimSuffix(string(numprocs_run), "\n")
    iostat_run, _ := exec.Command("bash", "-c", "iostat -dxkNy -c 1 1 | awk '{if (NR!=1 && NR!=2 && NR!=3 && NR!=4 && NR!=5 && NR!=6 && NF) { print $1\"|\"$4\"|\"$5\"|\"$6\"|\"$7 }}'").Output()
    iostat_res := strings.TrimSuffix(string(iostat_run), "\n")
    diskusedspace_run, _ := exec.Command("bash", "-c", "df -Ph --no-sync | awk '{if (NR!=1) { print $6\"|\"$5 }}' | cut -d '%' -f 1 | xargs").Output()
    diskusedspace_res := strings.TrimSuffix(string(diskusedspace_run), "\n")
    diskusedinode_run, _ := exec.Command("bash", "-c", "df -Pi --no-sync | awk '{if (NR!=1) { print $6\"|\"$5 }}' | cut -d '%' -f 1 | xargs").Output()
    diskusedinode_res := strings.TrimSuffix(string(diskusedinode_run), "\n")
    httpdreq_run, _ := exec.Command("bash", "-c", "httpd status | awk '/requests currently/ { print $1 }'").Output()
    httpdreq_res := strings.TrimSuffix(string(httpdreq_run), "\n")

    // System information
    hostname_run, _ := exec.Command("bash", "-c", "hostname").Output()
    hostname_res := strings.TrimSuffix(string(hostname_run), "\n")
    uptime_run, _ := exec.Command("bash", "-c", "awk '{ print $1 }' /proc/uptime").Output()
    uptime_res := strings.TrimSuffix(string(uptime_run), "\n")
    netlisten_run, _ := exec.Command("bash", "-c", "netstat -tlpn -A inet | awk '{if (NR!=1 && NR!=2) { print $4\"|\"$7 }}'").Output()
    netlisten_res := strings.TrimSuffix(string(netlisten_run), "\n")
    release_run, _ := exec.Command("bash", "-c", "cat /etc/redhat-release").Output()
    release_res := strings.TrimSuffix(string(release_run), "\n")
    uname_run, _ := exec.Command("bash", "-c", "uname -r").Output()
    uname_res := strings.TrimSuffix(string(uname_run), "\n")
    cpumodel_run, _ := exec.Command("bash", "-c", "grep 'model name' /proc/cpuinfo | head -n1 | cut -d ':' -f 2-").Output()
    cpumodel_res := strings.TrimSuffix(string(cpumodel_run), "\n")
    cpunum_run, _ := exec.Command("bash", "-c", "grep -c processor /proc/cpuinfo").Output()
    cpunum_res := strings.TrimSuffix(string(cpunum_run), "\n")

    // Package information
    pkg_push_run, _ := exec.Command("bash", "-c", "rpm -q inventory-push | grep -v 'not installed'").Output()
    pkg_push_res := strings.TrimSuffix(string(pkg_push_run), "\n")
    pkg_openssl_run, _ := exec.Command("bash", "-c", "rpm -q openssl | grep -v 'not installed'").Output()
    pkg_openssl_res := strings.TrimSuffix(string(pkg_openssl_run), "\n")
    pkg_opensshclient_run, _ := exec.Command("bash", "-c", "rpm -q openssh-clients | grep -v 'not installed'").Output()
    pkg_opensshclient_res := strings.TrimSuffix(string(pkg_opensshclient_run), "\n")
    pkg_opensshserver_run, _ := exec.Command("bash", "-c", "rpm -q openssh-server | grep -v 'not installed'").Output()
    pkg_opensshserver_res := strings.TrimSuffix(string(pkg_opensshserver_run), "\n")
    pkg_httpd_run, _ := exec.Command("bash", "-c", "rpm -q httpd | grep -v 'not installed'").Output()
    pkg_httpd_res := strings.TrimSuffix(string(pkg_httpd_run), "\n")
    pkg_nginx_run, _ := exec.Command("bash", "-c", "rpm -q nginx | grep -v 'not installed'").Output()
    pkg_nginx_res := strings.TrimSuffix(string(pkg_nginx_run), "\n")
    pkg_php_run, _ := exec.Command("bash", "-c", "php -v | awk 'NR==1 { print $2 }'").Output()
    pkg_php_res := strings.TrimSuffix(string(pkg_php_run), "\n")

    // Build our json string
    jsonData := map[string]string{"token": token, "timestamp": timestamp_res, "hostname": hostname_res, "uptime": uptime_res, "loadavg": loadavg_res, "diskusedspace": diskusedspace_res, "diskusedinode": diskusedinode_res, "iostat": iostat_res, "numprocs": numprocs_res, "netlisten": netlisten_res, "tcpnum": tcpnum_res, "udpnum": udpnum_res, "release": release_res, "uname": uname_res, "cpumodel": cpumodel_res, "cpunum": cpunum_res, "httpdreq": httpdreq_res, "netsar": netsar_res, "memtotal": memtotal_res, "memfree": memfree_res, "membuffers": membuffers_res, "memcached": memcached_res, "memavailable": memavailable_res, "swaptotal": swaptotal_res, "swapfree": swapfree_res, "mpstat": mpstat_res, "pkg_openssl": pkg_openssl_res, "pkg_opensshclient": pkg_opensshclient_res, "pkg_opensshserver": pkg_opensshserver_res, "pkg_httpd": pkg_httpd_res, "pkg_nginx": pkg_nginx_res, "pkg_php": pkg_php_res, "pkg_push": pkg_push_res}
    jsonValue, _ := json.Marshal(jsonData)

    // HTTPS POST with our TLS transport and basic auth
    client := &http.Client{Transport: transport}
    req, err := http.NewRequest("POST", apiurl, bytes.NewBuffer(jsonValue))
    req.SetBasicAuth(authuser, authpass)
    response, err := client.Do(req)

    // If we cant connect return an error, otherwise print the remote response
    if err != nil {
        fmt.Print("API-NOTCONNECT")
    } else {
        data, _ := ioutil.ReadAll(response.Body)
        fmt.Println(string(data))
    }
}
