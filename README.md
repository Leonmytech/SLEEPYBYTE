# SecureNotes 2.3.0

Build Android (APK) di SecureNotes, pubblicata come release separata.
Questo branch non condivide storia con `main` (progetto SleepyByte) e non contiene l'app macOS `.app`: contiene solo l'APK.

## File

- `SecureNotes-2.3.0.apk`: APK firmato, minSdk 26, targetSdk 35
- SHA-256: `91e6c366d5f1a4480fbdea8bdf2f75abf4590eda5d6df1bd3799bfdd4ec9811c`

## Correzioni

- **Crash allo sblocco del vault**: la barra di navigazione in basso richiamava se stessa all'infinito (`switchScreen` → `setSelectedItemId` → listener → `switchScreen`), causando uno `StackOverflowError`. Ora il tab selezionato viene aggiornato senza riattivare il listener.
- **Pulsanti +** (nuova nota, nuova password, aggiungi file): erano coperti dalla barra di navigazione; ora sono sopra la barra.

## Installazione

- La firma è diversa da quella delle versioni precedenti: **disinstalla prima l'app**. La disinstallazione cancella il vault locale, perché il backup è disabilitato (`allowBackup="false"`).
- Stato: firma e struttura dell'APK verificate, build ricompilata. Non ancora testata su dispositivo.
