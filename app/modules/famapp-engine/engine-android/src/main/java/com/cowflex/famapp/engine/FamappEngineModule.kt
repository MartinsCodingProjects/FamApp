package com.cowflex.famapp.engine

import com.cowflex.famapp.engine.core.EngineInfo
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

class FamappEngineModule : Module() {
    override fun definition() =
        ModuleDefinition {
            Name("FamappEngine")

            // Trivial bridge function (BUILDPLAN 1.5.4); the real repo interface follows in Run 2.
            Function("engineInfo") {
                val context = appContext.reactContext
                val stringsBundled =
                    context?.assets?.list("famapp/strings")?.contains("de.json") ?: false
                mapOf("coreVersion" to EngineInfo.VERSION, "stringsBundled" to stringsBundled)
            }
        }
}
