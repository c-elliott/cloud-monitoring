// https://github.com/c-elliott

// A monitoring agent implemented as a HTTPS webserver in go.lang
// with IP and hash based security, restricted to GET and request ratelimiting.

package main

import (
    "os"
    "os/exec"
    "syscall"
    "net"
    "net/http"
    "log"
    "time"
    "strings"
    "github.com/didip/tollbooth"
)

var (
    name = "simple-agent"
    version = "0.1 (09/06/2017)"
    startup = "simple-agent starting up."

    logfile = "/var/log/simple-agent.log"
    cert = "/opt/simple-agent/cert.pem"
    key = "/opt/simple-agent/key.pem"

    hashsecret = "zlsdhAhu38dsfj4NMdsha83aOPaifsdsdfjn12"

    port = "8888"
    allowedips = "127.0.0.1"
)

// A function to reliably get the client ip address
func GetClientIP(r *http.Request)  string {
    remoteIP := ""
    if parts := strings.Split(r.RemoteAddr, ":"); len(parts) == 2 {
        remoteIP = parts[0]
    }
    if xff := strings.Trim(r.Header.Get("X-Forwarded-For"), ","); len(xff) > 0 {
        addrs := strings.Split(xff, ",")
        lastFwd := addrs[len(addrs)-1]
        if ip := net.ParseIP(lastFwd); ip != nil {
            remoteIP = ip.String()
        }
    } else if xri := r.Header.Get("X-Real-Ip"); len(xri) > 0 {
        if ip := net.ParseIP(xri); ip != nil {
            remoteIP = ip.String()
        }
    }
    return remoteIP
}

// A function to handle everything passed from the webserver
func CommandHandler(w http.ResponseWriter, req *http.Request) {

    // Here we only allow HTTP GET requests
    switch req.Method {
    case "GET":

        // Checking if client IP is authorized
        ipauth := strings.Contains(allowedips,GetClientIP(req))
        if ipauth ==false {
            http.Error(w, "[403] Unauthorized", 403)
            log.Printf(GetClientIP(req) + " - [403] Unauthorized Source IP")
            return
        }

        // Data collection requests
        if req.URL.Path == string("/hash=" + hashsecret + "&fetch=" + "release") {
            out, _ := exec.Command("cat", "/etc/redhat-release").Output()
            w.Write([]byte(out))
        } else if req.URL.Path == string("/fetch=kernel") {
            out, _ := exec.Command("uname", "-r").Output()
            w.Write([]byte(out))
        } else if req.URL.Path == string("/fetch=rpmlist") {
            out, _ := exec.Command("rpm", "-qa").Output()
            w.Write([]byte(out))
        } else if req.URL.Path == string("/fetch=hostname") {
            out, _ := exec.Command("hostname").Output()
            w.Write([]byte(out))
        } else if req.URL.Path == string("/fetch=uptime") {
            out, _ := exec.Command("uptime").Output()
            w.Write([]byte(out))
        } else if req.URL.Path == string("/fetch=df") {
            out, _ := exec.Command("df", "-h").Output()
            w.Write([]byte(out))
        } else if req.URL.Path == string("/fetch=meminfo") {
            out, _ := exec.Command("cat", "/proc/meminfo").Output()
            w.Write([]byte(out))
        } else if req.URL.Path == string("/fetch=cpuinfo") {
            out, _ := exec.Command("cat", "/proc/cpuinfo").Output()
            w.Write([]byte(out))

        // Return HTTP Code 400 if no matching request
        } else {
            http.Error(w, "[400] Bad Request", 400)
            log.Printf(GetClientIP(req) + " - [400] Bad Request URL")
            return
        }

    // Return HTTP Code 405 if someone tries a method other than GET
    default:
        http.Error(w, "[405] Method Not Allowed", 405)
        log.Printf(GetClientIP(req) + " - [405] Method Not Allowed")
    }
}


// The main application starts here
func main() {

    // Open logfile for writing and write startup entries
    f, err := os.OpenFile(logfile, os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0644)
    if err != nil {
        log.Fatal(err)
    }
    defer f.Close()
    log.SetOutput(f)
    log.Printf(startup)
    log.Printf("version: " + version)

    // Exit if process started as UID 0 (root)
    if syscall.Getuid() == 0 {
        log.Fatal("Failed to start: simple-agent must not run as root!")
    }

    // Limit number of requests to prevent DoS and excessive resource use
    limiter := tollbooth.NewLimiter(10, time.Second)
    limiter.Message = "[429] Too Many Requests"

    // Start http server as TLS only, define handler and certificates
    s := &http.Server {
        Addr:           ":" + port,
        ReadTimeout:    10 * time.Second,
        WriteTimeout:   10 * time.Second,
        MaxHeaderBytes: 1 << 2,
    }
    http.Handle("/", tollbooth.LimitFuncHandler(limiter,CommandHandler))
    err = s.ListenAndServeTLS(cert, key)
    if err != nil {
        log.Fatal("Failed to start: ", err)
    }

}
