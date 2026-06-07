package com.matka.tracker

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView

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
            domStorageEnabled = true            // for favorites (localStorage)
            cacheMode = WebSettings.LOAD_DEFAULT
            loadWithOverviewMode = true
            useWideViewPort = false
            mediaPlaybackRequiresUserGesture = false
        }
        web.setBackgroundColor(0xFF0B0E1F.toInt())
        web.webViewClient = WebViewClient()
        web.loadUrl("file:///android_asset/index.html")

        // Hardware back: let the web app close its detail sheet first.
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
