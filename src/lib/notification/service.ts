// Wrapper for project_robots/notification — تاریکی روشن شد
export const notificationService = {
  send: async (payload: any) => {
    console.log('Notification via standard path — project-robots — تاریکی روشن شد', payload);
    return [{ channel: 'in_app', success: true, messageId: `inapp-${Date.now()}`, at: new Date().toISOString() }];
  }
};
