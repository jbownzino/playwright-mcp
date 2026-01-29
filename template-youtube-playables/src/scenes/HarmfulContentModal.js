import Phaser from 'phaser';

export class HarmfulContentModal extends Phaser.Scene
{
    constructor ()
    {
        super('HarmfulContentModal');
    }

    create (data)
    {
        const { message = 'This is harmful content', onClose } = data;
        
        // Create semi-transparent background overlay
        const overlay = this.add.rectangle(
            this.cameras.main.centerX,
            this.cameras.main.centerY,
            this.cameras.main.width,
            this.cameras.main.height,
            0x000000,
            0.7
        ).setDepth(100).setInteractive();

        // Create modal container
        const modalWidth = 600;
        const modalHeight = 300;
        const modalX = this.cameras.main.centerX;
        const modalY = this.cameras.main.centerY;

        // Modal background
        const modalBg = this.add.rectangle(
            modalX,
            modalY,
            modalWidth,
            modalHeight,
            0xffffff,
            0.95
        ).setDepth(101).setStrokeStyle(4, 0xff0000);

        // Warning icon or text
        const warningText = this.add.text(
            modalX,
            modalY - 80,
            '⚠️',
            {
                fontFamily: 'Arial',
                fontSize: 64,
                color: '#ff0000'
            }
        ).setDepth(102).setOrigin(0.5);

        // Message text
        const messageText = this.add.text(
            modalX,
            modalY,
            message,
            {
                fontFamily: 'Arial',
                fontSize: 32,
                color: '#000000',
                align: 'center',
                wordWrap: { width: modalWidth - 40 }
            }
        ).setDepth(102).setOrigin(0.5);

        // Close button
        const closeButton = this.add.rectangle(
            modalX,
            modalY + 100,
            200,
            60,
            0x333333
        ).setDepth(102).setInteractive({ useHandCursor: true });

        const closeButtonText = this.add.text(
            modalX,
            modalY + 100,
            'Close',
            {
                fontFamily: 'Arial',
                fontSize: 24,
                color: '#ffffff'
            }
        ).setDepth(103).setOrigin(0.5);

        // Close button hover effect
        closeButton.on('pointerover', () => {
            closeButton.setFillStyle(0x555555);
        });

        closeButton.on('pointerout', () => {
            closeButton.setFillStyle(0x333333);
        });

        // Close button click handler
        closeButton.on('pointerdown', () => {
            if (onClose) {
                onClose();
            }
            this.closeModalAndScheduleNext();
        });

        // Also close on overlay click
        overlay.on('pointerdown', () => {
            if (onClose) {
                onClose();
            }
            this.closeModalAndScheduleNext();
        });
        
        // Store reference to close button for external access
        this.closeButton = closeButton;

        // Animate modal appearance
        modalBg.setScale(0);
        this.tweens.add({
            targets: modalBg,
            scaleX: 1,
            scaleY: 1,
            duration: 300,
            ease: 'Back.easeOut'
        });

        warningText.setAlpha(0);
        messageText.setAlpha(0);
        closeButton.setAlpha(0);
        closeButtonText.setAlpha(0);

        this.tweens.add({
            targets: [warningText, messageText, closeButton, closeButtonText],
            alpha: 1,
            duration: 300,
            delay: 150
        });
    }
    
    closeModalAndScheduleNext ()
    {
        // Get the Game scene to schedule next harmful content
        const gameScene = this.scene.get('Game');
        if (gameScene)
        {
            // Reset shot counter for next harmful content
            gameScene.registry.set('totalShotsThrown', 0);
            
            // Schedule next harmful content modal
            gameScene.scheduleNextHarmfulContent();
            
            console.log('Modal closed - scheduled next harmful content modal');
        }
        
        // Close this modal scene
        this.scene.stop();
    }
}
