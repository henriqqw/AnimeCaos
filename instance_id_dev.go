//go:build dev

package main

// Keep the development window separate from the installed application. A
// stopped Vite server must not capture launches of the production build.
const appInstanceID = "com.animecaos.App.dev"
