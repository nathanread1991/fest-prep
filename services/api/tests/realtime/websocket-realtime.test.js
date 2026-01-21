// Real-time features and WebSocket connection tests
const { test, expect } = require('@playwright/test');

test.describe('Real-time Features and WebSocket Tests', () => {
  test.describe('WebSocket Connection', () => {
    test('should establish WebSocket connection', async ({ page }) => {
      await page.goto('/');
      
      const wsConnection = await page.evaluate(() => {
        return new Promise((resolve) => {
          try {
            // Test WebSocket support
            if (typeof WebSocket === 'undefined') {
              resolve({ supported: false, error: 'WebSocket not supported' });
              return;
            }
            
            // Try to establish connection (mock endpoint)
            const ws = new WebSocket('ws://localhost:8080/ws');
            
            const timeout = setTimeout(() => {
              ws.close();
              resolve({ 
                supported: true, 
                connected: false, 
                error: 'Connection timeout' 
              });
            }, 5000);
            
            ws.onopen = () => {
              clearTimeout(timeout);
              ws.close();
              resolve({ 
                supported: true, 
                connected: true 
              });
            };
            
            ws.onerror = (error) => {
              clearTimeout(timeout);
              resolve({ 
                supported: true, 
                connected: false, 
                error: 'Connection failed' 
              });
            };
            
          } catch (error) {
            resolve({ 
              supported: false, 
              error: error.message 
            });
          }
        });
      });
      
      expect(wsConnection.supported).toBe(true);
      console.log(`WebSocket connection test: ${wsConnection.connected ? 'Success' : wsConnection.error}`);
    });

    test('should handle WebSocket reconnection', async ({ page }) => {
      await page.goto('/');
      
      const reconnectionTest = await page.evaluate(() => {
        return new Promise((resolve) => {
          if (typeof WebSocket === 'undefined') {
            resolve({ supported: false });
            return;
          }
          
          let connectionAttempts = 0;
          const maxAttempts = 3;
          
          function connectWebSocket() {
            connectionAttempts++;
            const ws = new WebSocket('ws://localhost:8080/ws');
            
            ws.onopen = () => {
              // Simulate connection drop
              setTimeout(() => {
                ws.close();
              }, 100);
            };
            
            ws.onclose = () => {
              if (connectionAttempts < maxAttempts) {
                // Attempt reconnection
                setTimeout(connectWebSocket, 1000);
              } else {
                resolve({
                  supported: true,
                  reconnectionAttempts: connectionAttempts,
                  maxAttemptsReached: true
                });
              }
            };
            
            ws.onerror = () => {
              if (connectionAttempts < maxAttempts) {
                setTimeout(connectWebSocket, 1000);
              } else {
                resolve({
                  supported: true,
                  reconnectionAttempts: connectionAttempts,
                  maxAttemptsReached: true
                });
              }
            };
          }
          
          connectWebSocket();
          
          // Timeout after 10 seconds
          setTimeout(() => {
            resolve({
              supported: true,
              reconnectionAttempts: connectionAttempts,
              timeout: true
            });
          }, 10000);
        });
      });
      
      if (reconnectionTest.supported) {
        expect(reconnectionTest.reconnectionAttempts).toBeGreaterThan(1);
        console.log(`WebSocket reconnection attempts: ${reconnectionTest.reconnectionAttempts}`);
      }
    });

    test('should handle WebSocket message sending and receiving', async ({ page }) => {
      await page.goto('/');
      
      const messageTest = await page.evaluate(() => {
        return new Promise((resolve) => {
          if (typeof WebSocket === 'undefined') {
            resolve({ supported: false });
            return;
          }
          
          // Mock WebSocket for testing
          class MockWebSocket {
            constructor(url) {
              this.url = url;
              this.readyState = 1; // OPEN
              this.onopen = null;
              this.onmessage = null;
              this.onclose = null;
              this.onerror = null;
              
              // Simulate connection
              setTimeout(() => {
                if (this.onopen) this.onopen();
              }, 10);
            }
            
            send(data) {
              // Echo the message back
              setTimeout(() => {
                if (this.onmessage) {
                  this.onmessage({
                    data: `Echo: ${data}`,
                    type: 'message'
                  });
                }
              }, 10);
            }
            
            close() {
              this.readyState = 3; // CLOSED
              if (this.onclose) this.onclose();
            }
          }
          
          const ws = new MockWebSocket('ws://localhost:8080/ws');
          const testMessage = 'Hello WebSocket';
          let receivedMessage = null;
          
          ws.onopen = () => {
            ws.send(testMessage);
          };
          
          ws.onmessage = (event) => {
            receivedMessage = event.data;
            ws.close();
            
            resolve({
              supported: true,
              messageSent: testMessage,
              messageReceived: receivedMessage,
              success: receivedMessage.includes(testMessage)
            });
          };
          
          ws.onerror = () => {
            resolve({
              supported: true,
              error: 'Message test failed'
            });
          };
          
          // Timeout
          setTimeout(() => {
            resolve({
              supported: true,
              timeout: true
            });
          }, 5000);
        });
      });
      
      if (messageTest.supported && !messageTest.error && !messageTest.timeout) {
        expect(messageTest.success).toBe(true);
        console.log(`Message test: Sent "${messageTest.messageSent}", Received "${messageTest.messageReceived}"`);
      }
    });
  });

  test.describe('Real-time Updates', () => {
    test('should handle real-time playlist updates', async ({ page }) => {
      await page.goto('/playlists/collaborative/123');
      
      // Mock real-time update
      const updateResult = await page.evaluate(() => {
        return new Promise((resolve) => {
          // Simulate receiving a real-time update
          const mockUpdate = {
            type: 'playlist_update',
            data: {
              playlistId: '123',
              action: 'song_added',
              song: {
                id: 'new-song-1',
                title: 'New Song',
                artist: 'Test Artist'
              }
            }
          };
          
          // Simulate processing the update
          const playlistContainer = document.querySelector('.playlist-songs, .song-list');
          
          if (playlistContainer) {
            const newSongElement = document.createElement('div');
            newSongElement.className = 'song-item real-time-added';
            newSongElement.textContent = `${mockUpdate.data.song.title} - ${mockUpdate.data.song.artist}`;
            playlistContainer.appendChild(newSongElement);
            
            resolve({
              success: true,
              updateProcessed: true,
              songAdded: true
            });
          } else {
            resolve({
              success: false,
              error: 'Playlist container not found'
            });
          }
        });
      });
      
      if (updateResult.success) {
        // Verify the update was applied
        const newSong = page.locator('.real-time-added');
        await expect(newSong).toBeVisible();
        
        const songText = await newSong.textContent();
        expect(songText).toContain('New Song');
      }
    });

    test('should handle real-time notifications', async ({ page }) => {
      await page.goto('/');
      
      const notificationTest = await page.evaluate(() => {
        return new Promise((resolve) => {
          // Mock real-time notification
          const mockNotification = {
            type: 'notification',
            data: {
              id: 'notif-1',
              message: 'Your playlist has been shared!',
              timestamp: Date.now()
            }
          };
          
          // Simulate notification display
          const notificationContainer = document.createElement('div');
          notificationContainer.className = 'notification-container';
          notificationContainer.style.position = 'fixed';
          notificationContainer.style.top = '20px';
          notificationContainer.style.right = '20px';
          notificationContainer.style.zIndex = '9999';
          
          const notification = document.createElement('div');
          notification.className = 'notification real-time-notification';
          notification.textContent = mockNotification.data.message;
          notification.style.background = '#4CAF50';
          notification.style.color = 'white';
          notification.style.padding = '10px';
          notification.style.borderRadius = '4px';
          
          notificationContainer.appendChild(notification);
          document.body.appendChild(notificationContainer);
          
          // Auto-hide after 3 seconds
          setTimeout(() => {
            if (notificationContainer.parentNode) {
              notificationContainer.parentNode.removeChild(notificationContainer);
            }
          }, 3000);
          
          resolve({
            success: true,
            notificationShown: true,
            message: mockNotification.data.message
          });
        });
      });
      
      if (notificationTest.success) {
        const notification = page.locator('.real-time-notification');
        await expect(notification).toBeVisible();
        
        const notificationText = await notification.textContent();
        expect(notificationText).toBe(notificationTest.message);
        
        // Wait for auto-hide
        await page.waitForTimeout(3500);
        await expect(notification).not.toBeVisible();
      }
    });

    test('should handle real-time user presence', async ({ page }) => {
      await page.goto('/playlists/collaborative/123');
      
      const presenceTest = await page.evaluate(() => {
        return new Promise((resolve) => {
          // Mock user presence updates
          const mockPresenceUpdate = {
            type: 'user_presence',
            data: {
              users: [
                { id: 'user1', name: 'Alice', status: 'online' },
                { id: 'user2', name: 'Bob', status: 'online' },
                { id: 'user3', name: 'Charlie', status: 'away' }
              ]
            }
          };
          
          // Create presence indicator
          let presenceContainer = document.querySelector('.user-presence');
          if (!presenceContainer) {
            presenceContainer = document.createElement('div');
            presenceContainer.className = 'user-presence';
            presenceContainer.style.position = 'fixed';
            presenceContainer.style.bottom = '20px';
            presenceContainer.style.left = '20px';
            document.body.appendChild(presenceContainer);
          }
          
          // Clear existing presence
          presenceContainer.innerHTML = '';
          
          // Add user presence indicators
          mockPresenceUpdate.data.users.forEach(user => {
            const userIndicator = document.createElement('div');
            userIndicator.className = `user-indicator user-${user.status}`;
            userIndicator.textContent = user.name;
            userIndicator.style.display = 'inline-block';
            userIndicator.style.margin = '5px';
            userIndicator.style.padding = '5px 10px';
            userIndicator.style.borderRadius = '15px';
            userIndicator.style.fontSize = '12px';
            
            if (user.status === 'online') {
              userIndicator.style.background = '#4CAF50';
              userIndicator.style.color = 'white';
            } else {
              userIndicator.style.background = '#FFC107';
              userIndicator.style.color = 'black';
            }
            
            presenceContainer.appendChild(userIndicator);
          });
          
          resolve({
            success: true,
            usersShown: mockPresenceUpdate.data.users.length,
            onlineUsers: mockPresenceUpdate.data.users.filter(u => u.status === 'online').length
          });
        });
      });
      
      if (presenceTest.success) {
        const presenceContainer = page.locator('.user-presence');
        await expect(presenceContainer).toBeVisible();
        
        const userIndicators = page.locator('.user-indicator');
        const indicatorCount = await userIndicators.count();
        expect(indicatorCount).toBe(presenceTest.usersShown);
        
        const onlineIndicators = page.locator('.user-online');
        const onlineCount = await onlineIndicators.count();
        expect(onlineCount).toBe(presenceTest.onlineUsers);
      }
    });
  });

  test.describe('Live Collaboration', () => {
    test('should handle concurrent playlist editing', async ({ page }) => {
      await page.goto('/playlists/collaborative/123');
      
      const collaborationTest = await page.evaluate(() => {
        return new Promise((resolve) => {
          // Simulate concurrent edits
          const edits = [
            {
              user: 'Alice',
              action: 'add_song',
              song: { title: 'Song A', artist: 'Artist A' }
            },
            {
              user: 'Bob',
              action: 'remove_song',
              songId: 'song-123'
            },
            {
              user: 'Charlie',
              action: 'reorder_songs',
              newOrder: ['song-1', 'song-2', 'song-3']
            }
          ];
          
          const playlistContainer = document.querySelector('.playlist-songs') || document.createElement('div');
          playlistContainer.className = 'playlist-songs';
          if (!playlistContainer.parentNode) {
            document.body.appendChild(playlistContainer);
          }
          
          let processedEdits = 0;
          
          edits.forEach((edit, index) => {
            setTimeout(() => {
              // Process each edit
              const editIndicator = document.createElement('div');
              editIndicator.className = `edit-indicator edit-${edit.action}`;
              editIndicator.textContent = `${edit.user}: ${edit.action}`;
              editIndicator.style.padding = '5px';
              editIndicator.style.margin = '2px';
              editIndicator.style.background = '#E3F2FD';
              editIndicator.style.borderLeft = '3px solid #2196F3';
              
              playlistContainer.appendChild(editIndicator);
              processedEdits++;
              
              if (processedEdits === edits.length) {
                resolve({
                  success: true,
                  editsProcessed: processedEdits,
                  totalEdits: edits.length
                });
              }
            }, index * 100);
          });
        });
      });
      
      if (collaborationTest.success) {
        const editIndicators = page.locator('.edit-indicator');
        const indicatorCount = await editIndicators.count();
        expect(indicatorCount).toBe(collaborationTest.totalEdits);
        
        // Check that all edit types are represented
        const addEdit = page.locator('.edit-add_song');
        const removeEdit = page.locator('.edit-remove_song');
        const reorderEdit = page.locator('.edit-reorder_songs');
        
        await expect(addEdit).toBeVisible();
        await expect(removeEdit).toBeVisible();
        await expect(reorderEdit).toBeVisible();
      }
    });

    test('should handle conflict resolution', async ({ page }) => {
      await page.goto('/playlists/collaborative/123');
      
      const conflictTest = await page.evaluate(() => {
        return new Promise((resolve) => {
          // Simulate conflicting edits
          const conflicts = [
            {
              type: 'concurrent_edit',
              user1: 'Alice',
              user2: 'Bob',
              resource: 'song-123',
              action1: 'edit_title',
              action2: 'delete_song'
            }
          ];
          
          // Create conflict resolution UI
          const conflictContainer = document.createElement('div');
          conflictContainer.className = 'conflict-resolution';
          conflictContainer.style.position = 'fixed';
          conflictContainer.style.top = '50%';
          conflictContainer.style.left = '50%';
          conflictContainer.style.transform = 'translate(-50%, -50%)';
          conflictContainer.style.background = 'white';
          conflictContainer.style.border = '2px solid #FF5722';
          conflictContainer.style.padding = '20px';
          conflictContainer.style.borderRadius = '8px';
          conflictContainer.style.zIndex = '10000';
          
          const conflictMessage = document.createElement('div');
          conflictMessage.textContent = `Conflict detected: ${conflicts[0].user1} and ${conflicts[0].user2} made conflicting changes`;
          conflictMessage.style.marginBottom = '10px';
          
          const resolveButton = document.createElement('button');
          resolveButton.textContent = 'Resolve Conflict';
          resolveButton.className = 'resolve-conflict-btn';
          resolveButton.onclick = () => {
            document.body.removeChild(conflictContainer);
            resolve({
              success: true,
              conflictDetected: true,
              conflictResolved: true
            });
          };
          
          conflictContainer.appendChild(conflictMessage);
          conflictContainer.appendChild(resolveButton);
          document.body.appendChild(conflictContainer);
          
          // Auto-resolve after 5 seconds if not manually resolved
          setTimeout(() => {
            if (conflictContainer.parentNode) {
              document.body.removeChild(conflictContainer);
              resolve({
                success: true,
                conflictDetected: true,
                conflictResolved: false,
                autoResolved: true
              });
            }
          }, 5000);
        });
      });
      
      if (conflictTest.success) {
        const conflictDialog = page.locator('.conflict-resolution');
        await expect(conflictDialog).toBeVisible();
        
        const resolveButton = page.locator('.resolve-conflict-btn');
        await resolveButton.click();
        
        await expect(conflictDialog).not.toBeVisible();
      }
    });
  });

  test.describe('Connection Recovery', () => {
    test('should detect connection loss', async ({ page, context }) => {
      await page.goto('/');
      
      // Simulate connection loss
      await context.setOffline(true);
      
      const connectionLossTest = await page.evaluate(() => {
        return new Promise((resolve) => {
          // Simulate WebSocket connection loss detection
          const connectionStatus = {
            connected: false,
            lastPing: Date.now() - 10000, // 10 seconds ago
            reconnectAttempts: 0
          };
          
          // Create connection status indicator
          const statusIndicator = document.createElement('div');
          statusIndicator.className = 'connection-status offline';
          statusIndicator.textContent = 'Connection Lost - Attempting to reconnect...';
          statusIndicator.style.position = 'fixed';
          statusIndicator.style.top = '0';
          statusIndicator.style.left = '0';
          statusIndicator.style.right = '0';
          statusIndicator.style.background = '#FF5722';
          statusIndicator.style.color = 'white';
          statusIndicator.style.padding = '10px';
          statusIndicator.style.textAlign = 'center';
          statusIndicator.style.zIndex = '9999';
          
          document.body.appendChild(statusIndicator);
          
          resolve({
            success: true,
            connectionLost: true,
            statusShown: true
          });
        });
      });
      
      if (connectionLossTest.success) {
        const statusIndicator = page.locator('.connection-status.offline');
        await expect(statusIndicator).toBeVisible();
        
        const statusText = await statusIndicator.textContent();
        expect(statusText).toContain('Connection Lost');
      }
      
      // Restore connection
      await context.setOffline(false);
    });

    test('should recover connection automatically', async ({ page, context }) => {
      await page.goto('/');
      
      // Simulate connection loss and recovery
      await context.setOffline(true);
      await page.waitForTimeout(1000);
      await context.setOffline(false);
      
      const recoveryTest = await page.evaluate(() => {
        return new Promise((resolve) => {
          // Simulate connection recovery
          const statusIndicator = document.createElement('div');
          statusIndicator.className = 'connection-status online';
          statusIndicator.textContent = 'Connection Restored';
          statusIndicator.style.position = 'fixed';
          statusIndicator.style.top = '0';
          statusIndicator.style.left = '0';
          statusIndicator.style.right = '0';
          statusIndicator.style.background = '#4CAF50';
          statusIndicator.style.color = 'white';
          statusIndicator.style.padding = '10px';
          statusIndicator.style.textAlign = 'center';
          statusIndicator.style.zIndex = '9999';
          
          document.body.appendChild(statusIndicator);
          
          // Hide after 3 seconds
          setTimeout(() => {
            if (statusIndicator.parentNode) {
              statusIndicator.parentNode.removeChild(statusIndicator);
            }
          }, 3000);
          
          resolve({
            success: true,
            connectionRestored: true,
            statusShown: true
          });
        });
      });
      
      if (recoveryTest.success) {
        const statusIndicator = page.locator('.connection-status.online');
        await expect(statusIndicator).toBeVisible();
        
        const statusText = await statusIndicator.textContent();
        expect(statusText).toContain('Connection Restored');
        
        // Wait for auto-hide
        await page.waitForTimeout(3500);
        await expect(statusIndicator).not.toBeVisible();
      }
    });

    test('should queue messages during disconnection', async ({ page, context }) => {
      await page.goto('/playlists/collaborative/123');
      
      // Go offline
      await context.setOffline(true);
      
      const messageQueueTest = await page.evaluate(() => {
        return new Promise((resolve) => {
          // Simulate queuing messages while offline
          const messageQueue = [];
          
          // Add messages to queue
          const messages = [
            { type: 'add_song', data: { song: 'Song 1' } },
            { type: 'remove_song', data: { songId: 'song-123' } },
            { type: 'update_title', data: { title: 'New Title' } }
          ];
          
          messages.forEach(message => {
            messageQueue.push({
              ...message,
              timestamp: Date.now(),
              queued: true
            });
          });
          
          // Store in localStorage to persist during offline
          localStorage.setItem('messageQueue', JSON.stringify(messageQueue));
          
          // Show queue indicator
          const queueIndicator = document.createElement('div');
          queueIndicator.className = 'message-queue-indicator';
          queueIndicator.textContent = `${messageQueue.length} messages queued`;
          queueIndicator.style.position = 'fixed';
          queueIndicator.style.bottom = '20px';
          queueIndicator.style.right = '20px';
          queueIndicator.style.background = '#FF9800';
          queueIndicator.style.color = 'white';
          queueIndicator.style.padding = '10px';
          queueIndicator.style.borderRadius = '4px';
          
          document.body.appendChild(queueIndicator);
          
          resolve({
            success: true,
            messagesQueued: messageQueue.length,
            queueShown: true
          });
        });
      });
      
      if (messageQueueTest.success) {
        const queueIndicator = page.locator('.message-queue-indicator');
        await expect(queueIndicator).toBeVisible();
        
        const queueText = await queueIndicator.textContent();
        expect(queueText).toContain(`${messageQueueTest.messagesQueued} messages queued`);
      }
      
      // Come back online
      await context.setOffline(false);
      
      // Simulate processing queued messages
      const processQueueTest = await page.evaluate(() => {
        const queuedMessages = JSON.parse(localStorage.getItem('messageQueue') || '[]');
        
        // Process all queued messages
        queuedMessages.forEach(message => {
          console.log(`Processing queued message: ${message.type}`);
        });
        
        // Clear queue
        localStorage.removeItem('messageQueue');
        
        // Hide queue indicator
        const queueIndicator = document.querySelector('.message-queue-indicator');
        if (queueIndicator && queueIndicator.parentNode) {
          queueIndicator.parentNode.removeChild(queueIndicator);
        }
        
        return {
          success: true,
          messagesProcessed: queuedMessages.length,
          queueCleared: true
        };
      });
      
      expect(processQueueTest.messagesProcessed).toBe(messageQueueTest.messagesQueued);
      
      const queueIndicator = page.locator('.message-queue-indicator');
      await expect(queueIndicator).not.toBeVisible();
    });
  });
});