FILE(GLOB SDL_DLLS
	"C:/Program Files/SDL_ttf-2.0.10/lib/*.dll"
	"C:/Program Files/SDL_mixer-1.2.11/lib/*.dll"
	)
INSTALL( FILES
	"C:/Program Files/SDL-1.2.14/lib/SDL.dll"
	${SDL_DLLS}
	"C:/windows/system32/python26.dll"
	"C:/Program Files/openal-soft-1.12.854-bin/win32/OpenAL32.dll"
	DESTINATION ${CMAKE_INSTALL_PREFIX})
if (MINGW)
	INSTALL( FILES
		"C:/mingw32/bin/libgcc_s_sjlj-1.dll"
		"C:/mingw32/bin/libstdc++-6.dll"
		DESTINATION ${CMAKE_INSTALL_PREFIX})
ENDIF ()
