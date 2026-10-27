; -------------------------------------------------------------------
; Noesis PDF Reader Lite — Engine — Windows Installer (NSIS 3.x)
;
; Usage:
;   makensis installer.nsi
;   makensis /DVERSION=0.30.0 installer.nsi
;
; Produces: noesis-pdf-reader-lite-engine-${VERSION}-setup.exe
;
; The application is a CONSOLE tool (CLI + Textual TUI): the PyInstaller
; build does NOT use --windowed, so the .exe opens in the terminal.
; -------------------------------------------------------------------

!include "MUI2.nsh"
!include "FileFunc.nsh"

!ifndef VERSION
  !define VERSION "0.30.0"
!endif

!define PRODUCT_NAME      "Noesis PDF Reader Lite Engine"
!define PRODUCT_PUBLISHER "Noesis"
!define PRODUCT_WEB_SITE  "https://github.com/vigliafg/noesis-pdf-reader-lite"
!define PRODUCT_REGKEY    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define APP_EXE           "noesis-pdf-reader-lite-engine.exe"

Name             "${PRODUCT_NAME} ${VERSION}"
OutFile          "noesis-pdf-reader-lite-engine-${VERSION}-setup.exe"
InstallDir       "$PROGRAMFILES64\${PRODUCT_NAME}"
InstallDirRegKey HKLM "Software\${PRODUCT_NAME}" "InstallDir"
RequestExecutionLevel admin
SetCompressor    /SOLID lzma
BrandingText     " "

!define MUI_ABORTWARNING
!define MUI_ICON   "assets\noesis-pdf-reader-lite-engine.ico"
!define MUI_UNICON "assets\noesis-pdf-reader-lite-engine.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Italian"
!insertmacro MUI_RESERVEFILE_LANGDLL

LangString NAME_Desktop     ${LANG_ITALIAN} "Collegamento sul Desktop"
LangString NAME_StartMenu   ${LANG_ITALIAN} "Collegamento nel menu Start"
LangString NAME_App         ${LANG_ITALIAN} "${PRODUCT_NAME} (richiesto)"

LangString DESC_Desktop     ${LANG_ITALIAN} "Crea un'icona di collegamento sul Desktop."
LangString DESC_StartMenu   ${LANG_ITALIAN} "Crea un gruppo con i collegamenti nel menu Start."
LangString DESC_App         ${LANG_ITALIAN} "File principali dell'applicazione (CLI + TUI)."

LangString NAME_Desktop     ${LANG_ENGLISH} "Desktop shortcut"
LangString NAME_StartMenu   ${LANG_ENGLISH} "Start Menu shortcut"
LangString NAME_App         ${LANG_ENGLISH} "${PRODUCT_NAME} (required)"

LangString DESC_Desktop     ${LANG_ENGLISH} "Create a shortcut icon on the Desktop."
LangString DESC_StartMenu   ${LANG_ENGLISH} "Create a shortcut group in the Start Menu."
LangString DESC_App         ${LANG_ENGLISH} "Core application files (CLI + TUI)."

Section "$(NAME_App)" SectionApp
  SectionIn RO
  SetOutPath "$INSTDIR"
  SetOverwrite on
  File "dist\${APP_EXE}"

  WriteRegStr HKLM "Software\${PRODUCT_NAME}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\${PRODUCT_NAME}" "Version"    "${VERSION}"
  WriteUninstaller "$INSTDIR\uninst.exe"

  WriteRegStr   HKLM "${PRODUCT_REGKEY}" "DisplayName"     "${PRODUCT_NAME}"
  WriteRegStr   HKLM "${PRODUCT_REGKEY}" "UninstallString" '"$INSTDIR\uninst.exe"'
  WriteRegStr   HKLM "${PRODUCT_REGKEY}" "DisplayIcon"     '"$INSTDIR\${APP_EXE}"'
  WriteRegStr   HKLM "${PRODUCT_REGKEY}" "DisplayVersion"  "${VERSION}"
  WriteRegStr   HKLM "${PRODUCT_REGKEY}" "Publisher"       "${PRODUCT_PUBLISHER}"
  WriteRegStr   HKLM "${PRODUCT_REGKEY}" "URLInfoAbout"    "${PRODUCT_WEB_SITE}"
  WriteRegDWORD HKLM "${PRODUCT_REGKEY}" "EstimatedSize"   120000
  WriteRegDWORD HKLM "${PRODUCT_REGKEY}" "NoModify"        1
  WriteRegDWORD HKLM "${PRODUCT_REGKEY}" "NoRepair"        1
SectionEnd

Section /o "$(NAME_Desktop)" SectionDesktop
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
SectionEnd

Section "$(NAME_StartMenu)" SectionStartMenu
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut  "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortCut  "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk"       "$INSTDIR\uninst.exe"     "" "$INSTDIR\uninst.exe"     0
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SectionApp}       $(DESC_App)
  !insertmacro MUI_DESCRIPTION_TEXT ${SectionDesktop}   $(DESC_Desktop)
  !insertmacro MUI_DESCRIPTION_TEXT ${SectionStartMenu} $(DESC_StartMenu)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Section "Uninstall"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\uninst.exe"
  RMDir  "$INSTDIR"

  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk"
  RMDir  "$SMPROGRAMS\${PRODUCT_NAME}"

  DeleteRegKey HKLM "${PRODUCT_REGKEY}"
  DeleteRegKey HKLM "Software\${PRODUCT_NAME}"
SectionEnd
