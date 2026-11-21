package org.chromium.content_public.browser;
public interface WebContents {
    void evaluateJavaScript(String source, JavaScriptCallback callback);
}
