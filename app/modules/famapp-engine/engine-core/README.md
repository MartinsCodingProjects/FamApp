# engine-core

Pure Kotlin engine logic, no Android dependencies (README 8.1, BUILDPLAN A6): planner, levels, quiet hours, nag times, sync and conflict logic.

- Sources: `src/main/kotlin`. `engine-android/build.gradle` compiles them into the Android library.
- The standalone Gradle build with tests on the home server (JDK only) and its CI job are added in 2.2.
