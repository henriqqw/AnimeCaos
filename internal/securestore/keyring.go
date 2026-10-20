package securestore

import (
	"errors"

	"github.com/zalando/go-keyring"
)

const serviceName = "AnimeCaos"

var ErrNotFound = keyring.ErrNotFound

// Store is the small credential-vault contract used by account integrations.
// The production implementation delegates encryption and access control to
// Windows Credential Manager or Linux Secret Service.
type Store interface {
	Get(key string) (string, error)
	Set(key, value string) error
	Delete(key string) error
}

type System struct{}

func (System) Get(key string) (string, error) {
	return keyring.Get(serviceName, key)
}

func (System) Set(key, value string) error {
	return keyring.Set(serviceName, key, value)
}

func (System) Delete(key string) error {
	return keyring.Delete(serviceName, key)
}

func IsNotFound(err error) bool { return errors.Is(err, keyring.ErrNotFound) }
