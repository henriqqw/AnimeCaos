import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.animecaos.mobile"
    compileSdk = 35

    defaultConfig {
        val props = Properties()
        val localPropertiesFile = rootProject.file("local.properties")
        if (localPropertiesFile.exists()) {
            props.load(localPropertiesFile.inputStream())
        }

        val apiBaseUrl = (project.findProperty("apiBaseUrl") as String?)
            ?.trim()
            ?.takeIf { it.isNotEmpty() }
            ?: props.getProperty("apiBaseUrl")?.trim()?.takeIf { it.isNotEmpty() }
            ?: "http://10.0.0.4:8000/"

        applicationId = "com.animecaos.mobile"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    signingConfigs {
        create("release") {
            val props = Properties()
            val localPropertiesFile = rootProject.file("local.properties")
            if (localPropertiesFile.exists()) {
                props.load(localPropertiesFile.inputStream())
            }

            val keystorePath = props.getProperty("keystore.path")
            val keystorePassword = props.getProperty("keystore.password")
            val keyAliasName = props.getProperty("key.alias")
            val keyPasswordValue = props.getProperty("key.password")

            if (keystorePath != null && keystorePassword != null && keyAliasName != null && keyPasswordValue != null) {
                storeFile = file(keystorePath)
                storePassword = keystorePassword
                this.keyAlias = keyAliasName
                this.keyPassword = keyPasswordValue
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.09.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("androidx.activity:activity-compose:1.9.2")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.5")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.5")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.5")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("com.google.android.material:material:1.12.0")

    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    implementation("androidx.media3:media3-exoplayer:1.4.1")
    implementation("androidx.media3:media3-ui:1.4.1")
    implementation("io.coil-kt:coil-compose:2.7.0")

    testImplementation("junit:junit:4.13.2")
}
