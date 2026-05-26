-- AlterTable: add telegramId to User for Telegram coaching delivery
ALTER TABLE "User" ADD COLUMN "telegramId" TEXT;

-- CreateIndex: unique constraint on telegramId
CREATE UNIQUE INDEX "User_telegramId_key" ON "User"("telegramId");
