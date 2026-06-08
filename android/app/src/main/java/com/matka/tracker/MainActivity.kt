package com.matka.tracker

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView

    // The app screen is served from the web (GitHub Pages), so UI updates reach
    // every phone over-the-air with no reinstall. If the network is unavailable,
    // we fall back to the copy bundled inside the app.
    private val REMOTE_UI =
        "https://sourabhpal81.github.io/matka-tracker/app_ui/index.html"
    private val BUNDLED_UI = "file:///android_asset/index.html"

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        web = WebView(this)
        web.layoutParams = ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        )
        setContentView(web)

        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            cacheMode = WebSettings.LOAD_DEFAULT
            loadWithOverviewMode = true
            useWideViewPort = false
            mediaPlaybackRequiresUserGesture = false
        }
        web.setBackgroundColor(0xFF0B0E1F.toInt())

        web.webViewClient = object : WebViewClient() {
            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError
            ) {
                // Only fall back when the main page itself fails to load (offline).
                if (request.isForMainFrame) {
                    view.loadUrl(BUNDLED_UI)
                }
            }
        }

        // Cache-bust so a fresh screen is fetched each launch when online.
        web.loadUrl(REMOTE_UI + "?t=" + System.currentTimeMillis())

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                web.evaluateJavascript("(window.__back && window.__back()) || false") { result ->
                    if (result != "true") {
                        if (web.canGoBack()) web.goBack() else finish()
                    }
                }
            }
        })
    }
}
