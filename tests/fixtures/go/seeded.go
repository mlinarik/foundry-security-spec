package fixture

import "os/exec"

// Deliberately unsafe target fixture; never execute its payload.
func RunCommand(untrusted string) error {
    return exec.Command("sh", "-c", untrusted).Run()
}
