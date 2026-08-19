-- CreateEnum: external call source (currently just MetaSell)
CREATE TYPE "ExternalCallSource" AS ENUM ('METASELL');

-- CreateTable: append-only per-seller snapshot pulled from an external
-- aggregate-scoring source (Oisha-OS MetaSell conversion report). Not
-- attached to Call/Scorecard: MetaSell data is manager x time-window
-- aggregate, not per-call.
CREATE TABLE "ExternalScoreSnapshot" (
    "id" TEXT NOT NULL,
    "orgId" TEXT NOT NULL,
    "source" "ExternalCallSource" NOT NULL DEFAULT 'METASELL',
    "periodDays" INTEGER NOT NULL,
    "managerName" TEXT NOT NULL,
    "totalCalls" INTEGER NOT NULL,
    "convertedCalls" INTEGER NOT NULL,
    "conversionRate" DOUBLE PRECISION NOT NULL,
    "avgScore" DOUBLE PRECISION NOT NULL,
    "growthStage" TEXT,
    "growthStageLabel" TEXT,
    "revenueWon" DOUBLE PRECISION,
    "revenueAtRisk" DOUBLE PRECISION,
    "dealsWon" INTEGER,
    "dealsLost" INTEGER,
    "topWeaknesses" JSONB,
    "topObjections" JSONB,
    "raw" JSONB NOT NULL,
    "fetchedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ExternalScoreSnapshot_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ExternalScoreSnapshot_orgId_source_periodDays_fetchedAt_idx" ON "ExternalScoreSnapshot"("orgId", "source", "periodDays", "fetchedAt");

-- CreateIndex
CREATE INDEX "ExternalScoreSnapshot_orgId_managerName_idx" ON "ExternalScoreSnapshot"("orgId", "managerName");

-- AddForeignKey
ALTER TABLE "ExternalScoreSnapshot" ADD CONSTRAINT "ExternalScoreSnapshot_orgId_fkey" FOREIGN KEY ("orgId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;
