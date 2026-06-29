package com.zyl.stockanalyze.notification;

public interface NotificationSender {
    NotificationSender DISABLED = new NotificationSender() {
        @Override
        public boolean isEnabled() {
            return false;
        }

        @Override
        public void sendText(String message) {
            // no-op
        }
    };

    boolean isEnabled();

    void sendText(String message);
}
